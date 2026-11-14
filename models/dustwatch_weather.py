# -*- coding: utf-8 -*-
"""Forecast snapshots and privacy-preserving fleet weather signals.

The first version is deliberately explainable: it stores the provider forecast,
converts forecast solar radiation to peak-sun-hours, and looks for correlated
output shortfalls across independent customers. It does not autonomously book
cleaning work or present the regional heuristic as an official storm warning.
"""
import logging
import math
from collections import defaultdict
from datetime import timedelta

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .weather_utils import dubai_day_start_utc


_logger = logging.getLogger(__name__)
_PUBLIC_FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
_COMMERCIAL_FORECAST_URL = 'https://customer-api.open-meteo.com/v1/forecast'
_DAILY_VARIABLES = ','.join((
    'weather_code',
    'precipitation_sum',
    'precipitation_probability_max',
    'shortwave_radiation_sum',
    'wind_speed_10m_max',
))
_HOURLY_VARIABLES = ','.join((
    'relative_humidity_2m',
    'dew_point_2m',
    'temperature_2m',
    'precipitation_probability',
    'precipitation',
))


def _number(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def weather_code_label(code):
    """Human label for the common WMO codes returned by Open-Meteo."""
    if code is None:
        return _('Not available')
    code = int(code)
    if code == 0:
        return _('Clear')
    if code == 1:
        return _('Mostly clear')
    if code == 2:
        return _('Partly cloudy')
    if code == 3:
        return _('Overcast')
    if code in (30, 31, 32, 33, 34, 35, 98):
        return _('Dust or sand storm conditions')
    if code in (45, 48):
        return _('Fog')
    if code in (51, 53, 55, 56, 57):
        return _('Drizzle')
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return _('Rain or showers')
    if code in (95, 96, 99):
        return _('Thunderstorm')
    return _('Variable conditions')


class DustwatchWeatherSettings(models.TransientModel):
    _name = 'dustwatch.weather.settings'
    _description = 'DustWatch Weather Settings'

    weather_enabled = fields.Boolean(
        string='Enable weather forecasts',
        help='When enabled, Odoo sends each geolocated solar site coordinate to the selected weather provider.',
    )
    provider_mode = fields.Selection([
        ('public', 'Open-Meteo public preview (non-commercial only)'),
        ('commercial', 'Open-Meteo commercial API'),
    ], string='Provider plan', required=True, default='public')
    api_key = fields.Char(
        string='Commercial API key',
        groups='dustwatch.group_dustwatch_manager',
        help='Only needed for an Open-Meteo commercial subscription. It is stored in Odoo system parameters, not in source code.',
    )
    peer_signals_enabled = fields.Boolean(
        string='Contribute to anonymized fleet signals',
        help='Opt in to cross-customer aggregation. Only coarse-region counts and average output gaps are stored; site and customer names are never included in signals.',
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        params = self.env['ir.config_parameter'].sudo()
        values.update({
            'weather_enabled': params.get_param('dustwatch.weather.enabled', 'False') == 'True',
            'provider_mode': params.get_param('dustwatch.weather.provider_mode', 'public'),
            'api_key': params.get_param('dustwatch.weather.api_key', ''),
            'peer_signals_enabled': params.get_param('dustwatch.weather.peer_signals_enabled', 'False') == 'True',
        })
        return values

    def action_save_and_refresh(self):
        self.ensure_one()
        if self.weather_enabled and self.provider_mode == 'commercial' and not self.api_key:
            raise ValidationError(_('Enter the commercial Open-Meteo API key or choose the public preview plan.'))

        params = self.env['ir.config_parameter'].sudo()
        params.set_param('dustwatch.weather.enabled', str(bool(self.weather_enabled)))
        params.set_param('dustwatch.weather.provider_mode', self.provider_mode or 'public')
        params.set_param('dustwatch.weather.api_key', self.api_key or '')
        params.set_param('dustwatch.weather.peer_signals_enabled', str(bool(self.peer_signals_enabled)))

        stats = self.env['dustwatch.weather.forecast'].sudo()._cron_refresh_weather()
        if self.peer_signals_enabled:
            self.env['dustwatch.weather.signal'].sudo()._cron_analyze_regional_signals()
        if not self.weather_enabled:
            message = _('Weather is disabled; no site coordinates were sent to a provider.')
        elif stats.get('disabled'):
            message = _('Weather settings saved, but no geolocated active sites were found.')
        else:
            message = _(
                'Saved and refreshed %(sites)s sites. Created %(forecasts)s daily forecast snapshots; %(failures)s sites failed.',
                sites=stats.get('sites_updated', 0),
                forecasts=stats.get('forecast_rows', 0),
                failures=stats.get('failures', 0),
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('DustWatch weather'),
                'message': message,
                'type': 'warning' if stats.get('failures') else 'success',
                'sticky': bool(stats.get('failures')),
            },
        }


class DustwatchWeatherForecast(models.Model):
    _name = 'dustwatch.weather.forecast'
    _description = 'Solar Site Weather Forecast'
    _rec_name = 'site_id'
    _order = 'forecast_date asc, issued_at desc, id desc'

    site_id = fields.Many2one(
        'dustwatch.site', string='Solar site', required=True, index=True,
        ondelete='cascade',
    )
    reading_ids = fields.One2many(
        'dustwatch.reading', 'weather_forecast_id', string='Compared readings',
    )
    company_id = fields.Many2one(
        'res.company', related='site_id.company_id', store=True, index=True,
    )
    forecast_date = fields.Date(string='Forecast date', required=True, index=True)
    issued_at = fields.Datetime(string='Forecast captured at', required=True, index=True)
    provider = fields.Char(string='Weather provider', required=True, default='Open-Meteo')
    weather_code = fields.Integer(string='Weather code')
    weather_description = fields.Char(string='Conditions', compute='_compute_weather_description')
    precipitation_mm = fields.Float(string='Precipitation (mm)', digits=(16, 2))
    precipitation_probability = fields.Float(string='Rain chance (%)', digits=(16, 1))
    humidity_mean = fields.Float(string='Mean humidity (%)', digits=(16, 1))
    humidity_max = fields.Float(string='Maximum humidity (%)', digits=(16, 1))
    dew_risk_hours = fields.Float(string='Damp / near-dewpoint hours', digits=(16, 1))
    wind_speed_max = fields.Float(string='Maximum wind (km/h)', digits=(16, 1))
    shortwave_radiation_mj = fields.Float(string='Solar radiation (MJ/m²)', digits=(16, 2))
    peak_sun_hours = fields.Float(
        string='Forecast peak-sun hours', digits=(16, 2),
        help='Daily shortwave radiation converted from MJ/m² to equivalent kWh/m².',
    )
    forecast_expected_kwh = fields.Float(
        string='Planned output (kWh)', digits=(16, 2),
        compute='_compute_forecast_output', store=True,
    )

    _site_day_run_unique = models.Constraint(
        'UNIQUE(site_id, forecast_date, issued_at)',
        'A site can only have one record per weather forecast run and date.',
    )

    @api.depends('weather_code')
    def _compute_weather_description(self):
        for forecast in self:
            forecast.weather_description = weather_code_label(forecast.weather_code)

    @api.depends('peak_sun_hours', 'site_id.capacity_kwp', 'site_id.performance_factor')
    def _compute_forecast_output(self):
        for forecast in self:
            forecast.forecast_expected_kwh = max(
                forecast.site_id.capacity_kwp * forecast.peak_sun_hours * forecast.site_id.performance_factor,
                0.0,
            )

    @api.model
    def _weather_configuration(self):
        params = self.env['ir.config_parameter'].sudo()
        enabled = params.get_param('dustwatch.weather.enabled', 'False') == 'True'
        mode = params.get_param('dustwatch.weather.provider_mode', 'public')
        if mode == 'commercial':
            return enabled, mode, _COMMERCIAL_FORECAST_URL, params.get_param('dustwatch.weather.api_key', '')
        return enabled, 'public', _PUBLIC_FORECAST_URL, ''

    @api.model
    def _cron_refresh_weather(self):
        sites = self.env['dustwatch.site'].sudo().search([
            ('active', '=', True), ('latitude', '!=', 0), ('longitude', '!=', 0),
        ], order='id', limit=5000)
        return self._refresh_sites(sites)

    @api.model
    def _refresh_sites(self, sites):
        enabled, mode, endpoint, api_key = self._weather_configuration()
        if not enabled:
            return {'disabled': True, 'sites_updated': 0, 'forecast_rows': 0, 'failures': 0}
        if mode == 'commercial' and not api_key:
            _logger.warning('DustWatch weather refresh skipped: commercial provider key is missing.')
            return {'disabled': True, 'sites_updated': 0, 'forecast_rows': 0, 'failures': len(sites)}

        sites = sites.filtered(lambda site: site.active and site.latitude and site.longitude)
        stats = {'disabled': False, 'sites_updated': 0, 'forecast_rows': 0, 'failures': 0}
        # Coordinate lists let Open-Meteo return several locations in one
        # request. Keep chunks small to bound response size and cron runtime.
        for offset in range(0, len(sites), 20):
            chunk = sites[offset:offset + 20]
            query = {
                'latitude': ','.join('%.6f' % site.latitude for site in chunk),
                'longitude': ','.join('%.6f' % site.longitude for site in chunk),
                'daily': _DAILY_VARIABLES,
                'hourly': _HOURLY_VARIABLES,
                'timezone': 'Asia/Dubai',
                'forecast_days': 7,
            }
            if mode == 'commercial':
                query['apikey'] = api_key
            try:
                response = requests.get(endpoint, params=query, timeout=(5, 20))
                if not response.ok:
                    self._mark_weather_failure(chunk)
                    stats['failures'] += len(chunk)
                    _logger.warning(
                        'Open-Meteo weather request failed for %s site(s), HTTP %s.',
                        len(chunk), response.status_code,
                    )
                    continue
                payload = response.json()
            except (requests.RequestException, ValueError):
                self._mark_weather_failure(chunk)
                stats['failures'] += len(chunk)
                _logger.warning('Open-Meteo weather request failed for %s site(s).', len(chunk))
                continue

            if isinstance(payload, dict) and payload.get('error'):
                self._mark_weather_failure(chunk)
                stats['failures'] += len(chunk)
                _logger.warning('Open-Meteo returned an error for %s site(s).', len(chunk))
                continue
            payloads = payload if isinstance(payload, list) else [payload]
            if len(payloads) != len(chunk):
                self._mark_weather_failure(chunk)
                stats['failures'] += len(chunk)
                _logger.warning('Open-Meteo returned an unexpected location count for %s site(s).', len(chunk))
                continue

            issued_at = fields.Datetime.now()
            for site, location_data in zip(chunk, payloads):
                try:
                    rows = self._forecast_values_for_site(site, location_data, issued_at)
                    if rows:
                        self.sudo().create(rows)
                        site.sudo().write({
                            'weather_last_fetch_at': issued_at,
                            'weather_last_error': False,
                        })
                        stats['sites_updated'] += 1
                        stats['forecast_rows'] += len(rows)
                    else:
                        self._mark_weather_failure(site)
                        stats['failures'] += 1
                except (KeyError, TypeError, ValueError):
                    self._mark_weather_failure(site)
                    stats['failures'] += 1
                    _logger.warning('Open-Meteo response could not be parsed for solar site id=%s.', site.id)

        if sites:
            readings = self.env['dustwatch.reading'].sudo().search([
                ('site_id', 'in', sites.ids),
                ('date', '>=', fields.Date.context_today(self) - timedelta(days=30)),
            ])
            readings._attach_weather_forecasts()
        return stats

    @api.model
    def _forecast_values_for_site(self, site, payload, issued_at):
        daily = payload.get('daily') or {}
        hourly = payload.get('hourly') or {}
        days = daily.get('time') or []
        if not days:
            return []
        hourly_times = hourly.get('time') or []
        rows = []
        for index, day in enumerate(days):
            day_indices = [
                hour_index for hour_index, timestamp in enumerate(hourly_times)
                if timestamp[:10] == day
            ]
            humidity = [
                _number((hourly.get('relative_humidity_2m') or [])[i])
                for i in day_indices
                if i < len(hourly.get('relative_humidity_2m') or [])
                and (hourly.get('relative_humidity_2m') or [])[i] is not None
            ]
            dew_risk_hours = 0
            for hour_index in day_indices:
                humidity_values = hourly.get('relative_humidity_2m') or []
                dew_values = hourly.get('dew_point_2m') or []
                temp_values = hourly.get('temperature_2m') or []
                if not all(hour_index < len(values) for values in (humidity_values, dew_values, temp_values)):
                    continue
                if any(values[hour_index] is None for values in (humidity_values, dew_values, temp_values)):
                    continue
                rh, dew, temperature = map(_number, (
                    humidity_values[hour_index], dew_values[hour_index], temp_values[hour_index],
                ))
                if rh >= 85 or (rh >= 80 and temperature - dew <= 2.5):
                    dew_risk_hours += 1

            shortwave_mj = self._daily_value(daily, 'shortwave_radiation_sum', index)
            rows.append({
                'site_id': site.id,
                'forecast_date': fields.Date.to_date(day),
                'issued_at': issued_at,
                'provider': 'Open-Meteo',
                'weather_code': int(self._daily_value(daily, 'weather_code', index)),
                'precipitation_mm': self._daily_value(daily, 'precipitation_sum', index),
                'precipitation_probability': self._daily_value(daily, 'precipitation_probability_max', index),
                'humidity_mean': _mean(humidity),
                'humidity_max': max(humidity or [0.0]),
                'dew_risk_hours': dew_risk_hours,
                'wind_speed_max': self._daily_value(daily, 'wind_speed_10m_max', index),
                'shortwave_radiation_mj': shortwave_mj,
                'peak_sun_hours': max(shortwave_mj / 3.6, 0.0),
            })
        return rows

    @api.model
    def _daily_value(self, daily, name, index):
        values = daily.get(name) or []
        return _number(values[index]) if index < len(values) else 0.0

    @api.model
    def _mark_weather_failure(self, sites):
        for site in sites:
            site.sudo().write({
                'weather_last_fetch_at': fields.Datetime.now(),
                'weather_last_error': _('Weather provider request failed; check the Weather settings.'),
            })

    @api.model
    def _cron_prune_weather_history(self):
        cutoff = fields.Datetime.now() - timedelta(days=90)
        old = self.sudo().search([
            ('issued_at', '<', cutoff),
            ('reading_ids', '=', False),
        ], limit=50000)
        if old:
            old.unlink()
        signal_cutoff = fields.Date.context_today(self) - timedelta(days=365)
        old_signals = self.env['dustwatch.weather.signal'].sudo().search([
            ('signal_date', '<', signal_cutoff),
        ], limit=50000)
        if old_signals:
            old_signals.unlink()
        return True


class DustwatchWeatherSignal(models.Model):
    _name = 'dustwatch.weather.signal'
    _description = 'Anonymized Regional Weather Signal'
    _rec_name = 'name'
    _order = 'signal_date desc, signal_strength desc, id desc'

    name = fields.Char(string='Signal', required=True)
    signal_date = fields.Date(string='Reading date', required=True, index=True)
    region_bucket = fields.Char(string='Coarse region cell', required=True, index=True)
    event_type = fields.Selection([
        ('possible_dust_event', 'Possible dust / soiling event'),
        ('weather_related_output_drop', 'Rain or storm-related output drop'),
        ('regional_output_anomaly', 'Unclassified regional output anomaly'),
    ], string='Experimental signal', required=True)
    forecast_alignment = fields.Selection([
        ('windy_dry', 'Forecast is windy and dry'),
        ('rain_or_storm', 'Forecast includes rain or storm conditions'),
        ('no_clear_match', 'No clear weather match'),
    ], string='Official forecast comparison', required=True)
    site_count = fields.Integer(string='Participating sites', required=True)
    customer_count = fields.Integer(string='Independent customers', required=True)
    mean_shortfall_pct = fields.Float(string='Mean output shortfall (%)', digits=(16, 1), required=True)
    mean_wind_speed = fields.Float(string='Forecast wind (km/h)', digits=(16, 1))
    mean_precipitation_mm = fields.Float(string='Forecast precipitation (mm)', digits=(16, 1))
    mean_humidity_pct = fields.Float(string='Forecast humidity (%)', digits=(16, 1))
    signal_strength = fields.Float(
        string='Heuristic signal strength', digits=(16, 1),
        help='Rule-based indicator, not a calibrated weather probability.',
    )
    summary = fields.Text(string='Anonymized evidence', required=True)
    analysed_at = fields.Datetime(string='Analysed at', required=True, default=fields.Datetime.now)

    _region_day_unique = models.Constraint(
        'UNIQUE(signal_date, region_bucket)',
        'Only one regional signal is stored per date and coarse region.',
    )

    @api.model
    def _cron_analyze_regional_signals(self):
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param('dustwatch.weather.peer_signals_enabled', 'False') != 'True':
            return 0

        end_date = fields.Date.context_today(self)
        start_date = end_date - timedelta(days=3)
        readings = self.env['dustwatch.reading'].sudo().search([
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('weather_forecast_id', '!=', False),
        ], order='date, id')
        groups = defaultdict(list)
        for reading in readings:
            site = reading.site_id
            forecast = reading.weather_forecast_id
            expected = forecast.forecast_expected_kwh
            if not site.latitude or not site.longitude or expected < 1.0:
                continue
            shortfall = max(0.0, (expected - reading.actual_kwh) / expected * 100.0)
            if shortfall < 20.0:
                continue
            # 0.5-degree cells are deliberately coarse. Signals contain no
            # site IDs, coordinates, company IDs, or customer names.
            lat_cell = math.floor(site.latitude * 2)
            lon_cell = math.floor(site.longitude * 2)
            region_bucket = '%s:%s' % (lat_cell, lon_cell)
            groups[(reading.date, region_bucket)].append({
                'customer_id': reading.partner_id.commercial_partner_id.id,
                'shortfall': shortfall,
                'wind': forecast.wind_speed_max,
                'rain': forecast.precipitation_mm,
                'rain_probability': forecast.precipitation_probability,
                'humidity': forecast.humidity_mean,
                'weather_code': forecast.weather_code,
            })

        written = 0
        for (signal_date, region_bucket), evidence in groups.items():
            site_count = len(evidence)
            customer_count = len({item['customer_id'] for item in evidence if item['customer_id']})
            mean_shortfall = _mean(item['shortfall'] for item in evidence)
            if site_count < 3 or customer_count < 2 or mean_shortfall < 25.0:
                continue
            mean_wind = _mean(item['wind'] for item in evidence)
            mean_rain = _mean(item['rain'] for item in evidence)
            mean_rain_probability = _mean(item['rain_probability'] for item in evidence)
            mean_humidity = _mean(item['humidity'] for item in evidence)
            if mean_wind >= 25.0 and mean_rain < 1.0 and mean_humidity < 70.0:
                event_type = 'possible_dust_event'
                alignment = 'windy_dry'
            elif mean_rain >= 2.0 or mean_rain_probability >= 70.0 or any(
                item['weather_code'] in (95, 96, 99) for item in evidence
            ):
                event_type = 'weather_related_output_drop'
                alignment = 'rain_or_storm'
            else:
                event_type = 'regional_output_anomaly'
                alignment = 'no_clear_match'

            signal_strength = min(95.0, 30.0 + min(site_count, 10) * 5.0 + min(mean_shortfall, 50.0) * 0.5)
            event_labels = dict(self._fields['event_type'].selection)
            alignment_labels = dict(self._fields['forecast_alignment'].selection)
            vals = {
                'name': _('%(event)s · %(date)s', event=event_labels[event_type], date=signal_date),
                'signal_date': signal_date,
                'region_bucket': region_bucket,
                'event_type': event_type,
                'forecast_alignment': alignment,
                'site_count': site_count,
                'customer_count': customer_count,
                'mean_shortfall_pct': mean_shortfall,
                'mean_wind_speed': mean_wind,
                'mean_precipitation_mm': mean_rain,
                'mean_humidity_pct': mean_humidity,
                'signal_strength': signal_strength,
                'summary': _(
                    '%(sites)s sites across %(customers)s independent customers showed a mean %(gap).1f%% output shortfall against the stored weather-based plan. The provider forecast comparison is: %(alignment)s. This is an experimental regional anomaly signal, not an official dust-storm warning.',
                    sites=site_count,
                    customers=customer_count,
                    gap=mean_shortfall,
                    alignment=alignment_labels[alignment],
                ),
                'analysed_at': fields.Datetime.now(),
            }
            existing = self.sudo().search([
                ('signal_date', '=', signal_date),
                ('region_bucket', '=', region_bucket),
            ], limit=1)
            if existing:
                existing.write(vals)
            else:
                self.sudo().create(vals)
            written += 1
        return written
