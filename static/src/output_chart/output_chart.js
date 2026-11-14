/** @odoo-module **/

// Output chart of the site page (specification section 7.11).
//
// FR-CHT-01  a line chart with two series by date, "Expected (kWh)" and
//            "Actual (kWh)", for the site's latest 120 readings
// FR-CHT-02  each completed clean is marked on the date axis
// FR-CHT-03  the data comes only from get_chart_data() on dustwatch.site and
//            the chart uses Odoo's bundled Chart.js: no outside request
// FR-CHT-04  the chart follows the site shown and reloads with the page
//
// No formula is written here (ARC-05): the numbers are drawn as received.

import { Component, onWillStart, onWillUpdateProps, useEffect, useRef, useState } from "@odoo/owl";
import { loadBundle, loadJS } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const EXPECTED_COLOR = "#1f77b4"; // blue
const ACTUAL_COLOR = "#ff7f0e"; // orange
const CLEAN_COLOR = "#2ca02c"; // green
const CLEAN_LABEL = "Clean";

// Fields of the site page that change when the chart may have changed.
// When one of them differs, the data is fetched again.
const WATCHED_FIELDS = [
    "last_reading_date",
    "last_cleaned_date",
    "running_loss_kwh",
    "capacity_kwp",
    "performance_factor",
    "reading_count",
    "job_count",
];

/**
 * Load Chart.js as bundled with Odoo (ENV-04: no CDN link).
 *
 * Returns true when the library is ready. It never throws: if the chart
 * library cannot be loaded, the site page must still open, and the component
 * shows a short message instead of the chart.
 */
async function loadChartLibrary() {
    if (window.Chart) {
        return true;
    }
    try {
        await loadBundle("web.chartjs_lib");
    } catch {
        // Fall through to the direct file below.
    }
    if (!window.Chart) {
        try {
            // Same bundled file, loaded by its path.
            await loadJS("/web/static/lib/Chart/Chart.js");
        } catch {
            // Reported to the user by the template.
        }
    }
    return Boolean(window.Chart);
}

/**
 * A short text that identifies "this site, in this state".
 */
function recordSignature(record) {
    const values = WATCHED_FIELDS.map((name) => String(record.data[name]));
    return [record.resId, ...values].join("|");
}

/**
 * Turn the server data into what Chart.js draws.
 *
 * A clean can fall on a day without a reading (for example the day a job is
 * marked done). Such a day is added to the date axis with no value, so its
 * marker still has a place; the lines simply continue across it.
 */
function buildSeries(data) {
    const firstDay = data.labels[0];
    // ISO dates (YYYY-MM-DD) sort and compare correctly as plain text.
    const cleans = [...new Set(data.cleans)].filter((day) => day >= firstDay);
    const labels = [...new Set([...data.labels, ...cleans])].sort();
    const positionByDay = new Map(data.labels.map((day, index) => [day, index]));
    const pick = (values) =>
        labels.map((day) => (positionByDay.has(day) ? values[positionByDay.get(day)] : null));
    return {
        labels,
        expected: pick(data.expected),
        actual: pick(data.actual),
        cleans,
    };
}

/**
 * A small Chart.js plugin that draws one dashed vertical line, labelled
 * "Clean", on the date of every completed clean (FR-CHT-02).
 */
function cleanMarkerPlugin(cleans) {
    return {
        id: "dustwatchCleanMarkers",
        afterDatasetsDraw(chart) {
            const { ctx, chartArea, scales } = chart;
            if (!chartArea || !scales.x) {
                return;
            }
            ctx.save();
            ctx.strokeStyle = CLEAN_COLOR;
            ctx.fillStyle = CLEAN_COLOR;
            ctx.lineWidth = 1.5;
            ctx.setLineDash([6, 4]);
            ctx.font = "11px sans-serif";
            ctx.textBaseline = "top";
            for (const day of cleans) {
                const index = chart.data.labels.indexOf(day);
                if (index === -1) {
                    continue;
                }
                const x = scales.x.getPixelForValue(index);
                ctx.beginPath();
                ctx.moveTo(x, chartArea.top);
                ctx.lineTo(x, chartArea.bottom);
                ctx.stroke();
                // Write the label on the side where there is room.
                const nearRightEdge = x + 40 > chartArea.right;
                ctx.textAlign = nearRightEdge ? "right" : "left";
                ctx.fillText(CLEAN_LABEL, nearRightEdge ? x - 4 : x + 4, chartArea.top + 2);
            }
            ctx.restore();
        },
    };
}

export class DustwatchOutputChart extends Component {
    static template = "dustwatch.OutputChart";
    // The form view hands over the record being shown.
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.canvasRef = useRef("canvas");
        // data: what get_chart_data() returned; unavailable: true when the
        // chart library or the data could not be loaded.
        this.state = useState({ data: null, unavailable: false });
        this.chart = null;
        this.signature = null;
        this.libraryReady = false;

        // Before the first display: load Chart.js, then the data of the site.
        onWillStart(async () => {
            this.libraryReady = await loadChartLibrary();
            await this.loadData(this.props.record);
        });

        // When the form moves to another site, or the site is saved or
        // reloaded with new figures, fetch the data again (FR-CHT-04).
        onWillUpdateProps(async (nextProps) => {
            if (recordSignature(nextProps.record) !== this.signature) {
                await this.loadData(nextProps.record);
            }
        });

        // Draw after each display in which the data changed, and tidy up
        // the previous chart first.
        useEffect(
            () => {
                this.renderChart();
                return () => this.destroyChart();
            },
            () => [this.state.data]
        );
    }

    get hasData() {
        return Boolean(
            !this.state.unavailable && this.state.data && this.state.data.labels.length
        );
    }

    async loadData(record) {
        this.signature = recordSignature(record);
        let data = null;
        let unavailable = !this.libraryReady;
        // A site that is not saved yet has no id and nothing to chart.
        if (record.resId && this.libraryReady) {
            try {
                data = await this.orm.call("dustwatch.site", "get_chart_data", [[record.resId]]);
            } catch (error) {
                console.error("DustWatch: the output chart data could not be loaded", error);
                unavailable = true;
            }
        }
        this.state.unavailable = unavailable;
        this.state.data = data;
    }

    destroyChart() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }

    renderChart() {
        this.destroyChart();
        const canvas = this.canvasRef.el;
        if (!canvas || !this.hasData) {
            return;
        }
        try {
            this.chart = this.createChart(canvas);
        } catch (error) {
            // A drawing problem must never block the rest of the site page.
            console.error("DustWatch: the output chart could not be drawn", error);
        }
    }

    createChart(canvas) {
        const series = buildSeries(this.state.data);
        const lineStyle = {
            borderWidth: 2,
            pointRadius: 0,
            pointHitRadius: 8,
            tension: 0.2,
            spanGaps: true,
        };
        return new window.Chart(canvas, {
            type: "line",
            data: {
                labels: series.labels,
                datasets: [
                    {
                        label: "Expected (kWh)",
                        data: series.expected,
                        borderColor: EXPECTED_COLOR,
                        backgroundColor: EXPECTED_COLOR,
                        ...lineStyle,
                    },
                    {
                        label: "Actual (kWh)",
                        data: series.actual,
                        borderColor: ACTUAL_COLOR,
                        backgroundColor: ACTUAL_COLOR,
                        ...lineStyle,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { display: true, position: "top" },
                },
                scales: {
                    x: { ticks: { maxTicksLimit: 12, maxRotation: 0 } },
                    y: { title: { display: true, text: "kWh" } },
                },
            },
            plugins: [cleanMarkerPlugin(series.cleans)],
        });
    }
}

// Makes <widget name="dustwatch_output_chart"/> available in views.
registry.category("view_widgets").add("dustwatch_output_chart", {
    component: DustwatchOutputChart,
});
