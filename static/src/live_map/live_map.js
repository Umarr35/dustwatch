/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const REFRESH_MS = 15000;
const DUBAI_CENTER = { lat: 25.2048, lng: 55.2708 };
const SITE_FIELDS = [
    "name", "active", "partner_id", "status", "fault_suspected", "capacity_kwp",
    "latitude", "longitude", "currency_id", "cleaning_cost", "price_per_kwh",
    "running_loss", "running_loss_kwh", "avg_daily_loss", "current_loss_pct",
    "trigger_pct", "dust_rate_pct", "days_since_clean", "days_to_trigger",
    "last_cleaned_date", "last_reading_date", "open_job_id", "reading_count", "job_count",
];

const MAP_STYLE = [
    { elementType: "geometry", stylers: [{ color: "#18181b" }] },
    { elementType: "labels.text.fill", stylers: [{ color: "#a1a1aa" }] },
    { elementType: "labels.text.stroke", stylers: [{ color: "#18181b" }] },
    { featureType: "administrative.country", elementType: "geometry.stroke", stylers: [{ color: "#3f3f46" }] },
    { featureType: "administrative.locality", elementType: "labels.text.fill", stylers: [{ color: "#d4d4d8" }] },
    { featureType: "poi", stylers: [{ visibility: "off" }] },
    { featureType: "road", elementType: "geometry", stylers: [{ color: "#27272a" }] },
    { featureType: "road.arterial", elementType: "geometry", stylers: [{ color: "#3f3f46" }] },
    { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#52525b" }] },
    { featureType: "transit", stylers: [{ visibility: "off" }] },
    { featureType: "water", elementType: "geometry", stylers: [{ color: "#0f172a" }] },
];

function hasCoordinates(site) {
    return Number.isFinite(Number(site.latitude)) && Number.isFinite(Number(site.longitude))
        && Number(site.latitude) !== 0 && Number(site.longitude) !== 0;
}

function statusColor(status) {
    return ({ red: "#f97316", amber: "#fbbf24", green: "#22c55e" })[status] || "#f97316";
}

function statusLabel(status) {
    return ({ red: "Clean due", amber: "Approaching", green: "On track" })[status] || "No data";
}

function mapsPromise(apiKey) {
    if (window.google?.maps) {
        return Promise.resolve(window.google.maps);
    }
    if (!window.__dustwatchMapsPromise) {
        window.__dustwatchMapsPromise = new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.async = true;
            script.defer = true;
            script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&v=weekly`;
            script.onload = () => {
                if (!window.google?.maps) {
                    delete window.__dustwatchMapsPromise;
                    reject(new Error("Google Maps loaded without its map library."));
                    return;
                }
                resolve(window.google.maps);
            };
            script.onerror = () => {
                delete window.__dustwatchMapsPromise;
                reject(new Error("Google Maps could not be loaded."));
            };
            document.head.appendChild(script);
        });
    }
    return window.__dustwatchMapsPromise;
}

export class DustwatchLiveMap extends Component {
    static template = "dustwatch.LiveMap";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.mapRef = useRef("googleMap");
        this.state = useState({
            sites: [],
            selectedId: false,
            history: [],
            historyTab: "all",
            query: "",
            statusFilter: "all",
            loading: true,
            historyLoading: false,
            mapMode: "canvas",
            mapMessage: "",
            mapKeyMissing: false,
            lastUpdated: "—",
            live: false,
            zoom: 1,
            error: "",
        });
        this.map = null;
        this.markers = new Map();
        this.didFitBounds = false;
        this.refreshTimer = null;

        onWillStart(async () => {
            await this.refreshSites();
        });
        onMounted(async () => {
            await this.initializeGoogleMap();
            this.refreshTimer = setInterval(() => this.refreshSites(), REFRESH_MS);
        });
        onWillUnmount(() => {
            clearInterval(this.refreshTimer);
            this.markers.forEach((marker) => marker.setMap(null));
            this.markers.clear();
            this.map = null;
        });
    }

    get actionContext() {
        return this.props.action?.context || {};
    }

    get selectedSite() {
        return this.state.sites.find((site) => site.id === this.state.selectedId) || false;
    }

    get locatedSites() {
        return this.filteredSites.filter(hasCoordinates);
    }

    get filteredSites() {
        const query = this.state.query.trim().toLowerCase();
        return this.state.sites.filter((site) => {
            const matchesStatus = this.state.statusFilter === "all" || site.status === this.state.statusFilter;
            const partner = (site.partner_id?.[1] || "").toLowerCase();
            const matchesQuery = !query || site.name.toLowerCase().includes(query) || partner.includes(query);
            return matchesStatus && matchesQuery;
        });
    }

    get filteredHistory() {
        if (this.state.historyTab === "all") return this.state.history;
        return this.state.history.filter((entry) => entry.type === this.state.historyTab);
    }

    get stats() {
        const sites = this.state.sites;
        return {
            total: sites.length,
            due: sites.filter((site) => site.status === "red").length,
            approaching: sites.filter((site) => site.status === "amber").length,
            inspect: sites.filter((site) => site.fault_suspected).length,
            dailyLoss: sites.reduce((total, site) => total + Number(site.avg_daily_loss || 0), 0),
        };
    }

    async refreshSites() {
        const domain = [["active", "=", true]];
        const partnerId = Number(this.actionContext.dustwatch_partner_id || 0);
        if (partnerId) domain.push(["partner_id", "=", partnerId]);
        try {
            const sites = await this.orm.searchRead(
                "dustwatch.site",
                domain,
                SITE_FIELDS,
                { order: "urgency_sequence,avg_daily_loss desc,id", limit: 5000 }
            );
            this.state.sites = sites;
            this.state.error = "";
            this.state.live = true;
            this.state.lastUpdated = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

            const preferredId = Number(this.actionContext.dustwatch_site_id || this.state.selectedId || 0);
            const initialSite = sites.find((site) => site.id === preferredId) || sites[0];
            if (initialSite && !this.state.selectedId) {
                this.state.selectedId = initialSite.id;
            }
            if (this.state.selectedId && !sites.some((site) => site.id === this.state.selectedId)) {
                this.state.selectedId = initialSite?.id || false;
            }
            this.syncGoogleMarkers();
            if (this.state.selectedId) await this.loadHistory(this.state.selectedId);
        } catch (error) {
            console.error("DustWatch: live fleet refresh failed", error);
            this.state.error = "The live fleet could not be refreshed. Check your DustWatch access and retry.";
            this.state.live = false;
        } finally {
            this.state.loading = false;
        }
    }

    async loadHistory(siteId) {
        this.state.historyLoading = true;
        try {
            const domain = [["site_id", "=", siteId]];
            const [readings, jobs] = await Promise.all([
                this.orm.searchRead("dustwatch.reading", domain, [
                    "date", "actual_kwh", "expected_kwh", "lost_kwh", "loss_pct", "lost_aed",
                ], { order: "date desc,id desc", limit: 5000 }),
                this.orm.searchRead("dustwatch.cleaning.job", domain, [
                    "name", "state", "recommended_date", "scheduled_date", "date_done", "cost",
                    "recovery_state", "recovery_per_day", "payback_days", "explanation", "crew_user_id",
                ], { order: "id desc", limit: 5000 }),
            ]);
            const history = [
                ...readings.map((reading) => ({
                    type: "reading",
                    date: reading.date,
                    sortDate: reading.date || "",
                    title: "Daily output reading",
                    detail: `${this.number(reading.actual_kwh)} kWh actual · ${this.number(reading.expected_kwh)} kWh expected`,
                    result: `${this.number(reading.loss_pct, 1)}% loss · ${this.money(reading.lost_aed)}`,
                })),
                ...jobs.map((job) => ({
                    type: "cleaning",
                    date: job.date_done || job.scheduled_date || job.recommended_date,
                    sortDate: job.date_done || job.scheduled_date || job.recommended_date || "",
                    title: `${job.name} · ${this.selectionLabel(job.state)}`,
                    detail: `Clean cost ${this.money(job.cost)} · ${this.selectionLabel(job.recovery_state)}`,
                    result: job.payback_days ? `Payback ${this.number(job.payback_days, 1)} days` : "Result pending",
                    explanation: job.explanation || "",
                })),
            ].sort((a, b) => b.sortDate.localeCompare(a.sortDate));
            if (this.state.selectedId === siteId) this.state.history = history;
        } catch (error) {
            console.error("DustWatch: site history could not be loaded", error);
            this.state.history = [];
        } finally {
            this.state.historyLoading = false;
        }
    }

    async initializeGoogleMap() {
        try {
            const response = await rpc("/website/google_maps_api_key");
            const settings = typeof response === "string" ? JSON.parse(response) : response;
            const apiKey = settings?.google_maps_api_key || "";
            if (!apiKey) {
                this.state.mapKeyMissing = true;
                this.state.mapMessage = "Add a Google Maps API key in Website settings to enable live street tiles. Site pins remain interactive.";
                return;
            }
            await mapsPromise(apiKey);
            if (!this.mapRef.el) return;
            this.map = new window.google.maps.Map(this.mapRef.el, {
                center: DUBAI_CENTER,
                zoom: 10,
                styles: MAP_STYLE,
                disableDefaultUI: true,
                zoomControl: true,
                fullscreenControl: false,
                mapTypeControl: false,
                streetViewControl: false,
                clickableIcons: false,
                gestureHandling: "greedy",
                backgroundColor: "#09090b",
            });
            this.state.mapMode = "google";
            this.state.mapMessage = "";
            this.state.mapKeyMissing = false;
            this.map.addListener("click", () => this.selectSite(false));
            this.syncGoogleMarkers();
        } catch (error) {
            console.warn("DustWatch: Google Maps unavailable; using the Dubai coordinate map", error);
            this.state.mapKeyMissing = false;
            this.state.mapMessage = "Street map could not load. The coordinate map is still live and selectable.";
        }
    }

    syncGoogleMarkers() {
        if (!this.map) return;
        const visible = this.locatedSites;
        const visibleIds = new Set(visible.map((site) => site.id));
        for (const [id, marker] of this.markers.entries()) {
            if (!visibleIds.has(id)) {
                marker.setMap(null);
                this.markers.delete(id);
            }
        }
        for (const site of visible) {
            const position = { lat: Number(site.latitude), lng: Number(site.longitude) };
            let marker = this.markers.get(site.id);
            if (!marker) {
                marker = new window.google.maps.Marker({ map: this.map, position });
                marker.addListener("click", () => this.selectSite(site.id));
                this.markers.set(site.id, marker);
            } else {
                marker.setPosition(position);
            }
            marker.setTitle(site.name);
            marker.setIcon({
                path: window.google.maps.SymbolPath.CIRCLE,
                scale: site.id === this.state.selectedId ? 11 : 8,
                fillColor: statusColor(site.status),
                fillOpacity: 1,
                strokeColor: "#ffffff",
                strokeWeight: 2,
            });
        }
        if (!this.didFitBounds && visible.length) {
            const bounds = new window.google.maps.LatLngBounds();
            visible.forEach((site) => bounds.extend({ lat: Number(site.latitude), lng: Number(site.longitude) }));
            if (visible.length === 1) {
                this.map.setCenter({ lat: Number(visible[0].latitude), lng: Number(visible[0].longitude) });
                this.map.setZoom(12);
            } else {
                this.map.fitBounds(bounds, 56);
            }
            this.didFitBounds = true;
        }
    }

    async selectSite(siteId) {
        this.state.selectedId = siteId || false;
        this.syncGoogleMarkers();
        if (siteId) await this.loadHistory(siteId);
        else this.state.history = [];
    }

    setFilter(status) {
        this.state.statusFilter = status;
        this.syncGoogleMarkers();
    }

    setHistoryTab(tab) {
        this.state.historyTab = tab;
    }

    nodeStyle(site) {
        const lng = Number(site.longitude);
        const lat = Number(site.latitude);
        const left = Math.max(5, Math.min(95, 8 + ((lng - 54.90) / 0.72) * 84));
        const top = Math.max(6, Math.min(94, 92 - ((lat - 24.78) / 0.70) * 84));
        return `left:${left}%;top:${top}%;--node-color:${statusColor(site.status)}`;
    }

    selectFromSearch(siteId) {
        this.selectSite(siteId);
        const site = this.state.sites.find((record) => record.id === siteId);
        if (site && this.map && hasCoordinates(site)) {
            this.map.panTo({ lat: Number(site.latitude), lng: Number(site.longitude) });
            this.map.setZoom(Math.max(this.map.getZoom() || 10, 12));
        }
    }

    openSite() {
        if (!this.selectedSite) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: this.selectedSite.name,
            res_model: "dustwatch.site",
            res_id: this.selectedSite.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openReadings() {
        if (!this.selectedSite) return;
        const action = await this.orm.call("dustwatch.site", "action_view_readings", [[this.selectedSite.id]]);
        this.action.doAction(action);
    }

    async openJobs() {
        if (!this.selectedSite) return;
        const action = await this.orm.call("dustwatch.site", "action_view_jobs", [[this.selectedSite.id]]);
        this.action.doAction(action);
    }

    async openSimulator() {
        if (!this.selectedSite) return;
        const action = await this.orm.call("dustwatch.site", "action_open_simulator", [[this.selectedSite.id]]);
        this.action.doAction(action);
    }

    openFleet() {
        this.action.doAction("dustwatch.action_dustwatch_site_fleet");
    }

    openCleaningJobs() {
        this.action.doAction("dustwatch.action_dustwatch_cleaning_job");
    }

    openAllReadings() {
        this.action.doAction("dustwatch.action_dustwatch_reading");
    }

    zoomFallback(delta) {
        this.state.zoom = Math.max(1, Math.min(1.8, this.state.zoom + delta));
    }

    number(value, digits = 1) {
        return Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: digits });
    }

    statusLabel(status) {
        return statusLabel(status);
    }

    money(value) {
        const currency = this.selectedSite?.currency_id?.[1] || "AED";
        try {
            return new Intl.NumberFormat("en", { style: "currency", currency, maximumFractionDigits: 2 }).format(Number(value || 0));
        } catch {
            return `${this.number(value, 2)} ${currency}`;
        }
    }

    selectionLabel(value) {
        return (value || "pending").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    }
}

registry.category("actions").add("dustwatch.live_map", DustwatchLiveMap);
