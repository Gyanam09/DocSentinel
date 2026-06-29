"use client";

import { useState } from "react";

type Step = "form" | "loading" | "done" | "error";

type BBox = {
    min_lat: number;
    max_lat: number;
    min_lon: number;
    max_lon: number;
};

const sizeLabels: Record<string, string> = {
    "1": "Small - ~5x5 km",
    "2": "Medium - ~10x10 km",
    "3": "Large - ~20x20 km",
};

function generateBbox(lat: number, lon: number, size: string): BBox {
    const radii: Record<string, number> = { "1": 2.5, "2": 5.0, "3": 10.0 };
    const r = radii[size] || 2.5;
    const dLat = r / 111.0;
    const dLon = r / (111.0 * Math.abs(Math.cos((lat * Math.PI) / 180)));

    return {
        min_lat: +(lat - dLat).toFixed(6),
        max_lat: +(lat + dLat).toFixed(6),
        min_lon: +(lon - dLon).toFixed(6),
        max_lon: +(lon + dLon).toFixed(6),
    };
}

function isValidEmail(email: string) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export default function Home() {
    const [step, setStep] = useState<Step>("form");
    const [form, setForm] = useState({
        lat: "",
        lon: "",
        size: "1",
        scene_date: "2026-05-28",
        client_email: "",
    });
    const [jobId, setJobId] = useState("");
    const [error, setError] = useState("");
    const [bbox, setBbox] = useState<BBox | null>(null);

    async function handleSubmit() {
        const lat = Number(form.lat);
        const lon = Number(form.lon);

        if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
            setError("Please enter a latitude between -90 and 90.");
            setStep("error");
            return;
        }
        if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
            setError("Please enter a longitude between -180 and 180.");
            setStep("error");
            return;
        }
        if (Math.abs(lat) >= 89.9) {
            setError("Choose a point farther from the poles for automatic area generation.");
            setStep("error");
            return;
        }
        if (!isValidEmail(form.client_email.trim())) {
            setError("Please enter a valid email address.");
            setStep("error");
            return;
        }

        const box = generateBbox(lat, lon, form.size);
        setBbox(box);
        setStep("loading");
        setError("");

        try {
            const res = await fetch("/api/trigger", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    ...box,
                    scene_date: form.scene_date,
                    client_email: form.client_email.trim(),
                }),
            });
            const data = await res.json();
            if (!res.ok || !data.job_id) {
                throw new Error(data.error || "Unable to trigger the pipeline.");
            }
            setJobId(data.job_id);
            setStep("done");
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Unable to trigger the pipeline.");
            setStep("error");
        }
    }

    return (
        <main className="min-h-screen bg-[#080f1a] text-slate-200 flex flex-col items-center justify-center p-6">
            <div className="mb-8 text-center">
                <div className="flex items-center justify-center gap-3 mb-3">
                    <div className="w-8 h-8 rounded-full border-2 border-sky-400 flex items-center justify-center">
                        <div className="w-2 h-2 bg-sky-400 rounded-full" />
                    </div>
                    <span className="font-mono text-sky-400 tracking-widest text-sm uppercase">
                        DocSentinel
                    </span>
                </div>
                <h1 className="text-3xl font-bold text-white mb-2">
                    Land Intelligence Platform
                </h1>
                <p className="text-slate-400 text-sm max-w-md">
                    Enter location coordinates to generate a satellite land analysis report with NDVI,
                    terrain, soil, weather, infrastructure, and more.
                </p>
            </div>

            <div className="w-full max-w-md bg-[#0d2137] border border-[#1e3a5f] rounded-lg p-7">
                {(step === "form" || step === "error") && (
                    <>
                        <div className="text-xs font-mono text-sky-400 uppercase tracking-widest mb-5 pb-3 border-b border-[#1e3a5f]">
                            Step 1 - Enter coordinates
                        </div>

                        <div className="mb-4">
                            <label className="block text-xs text-slate-400 font-mono uppercase tracking-wider mb-1">
                                Latitude
                            </label>
                            <input
                                type="number"
                                step="0.000001"
                                min="-90"
                                max="90"
                                placeholder="e.g. 23.189"
                                value={form.lat}
                                onChange={(e) => setForm((f) => ({ ...f, lat: e.target.value }))}
                                className="w-full bg-[#080f1a] border border-[#1e3a5f] rounded-md px-3 py-2.5 text-sm text-sky-300 font-mono focus:border-sky-400 focus:outline-none"
                            />
                        </div>

                        <div className="mb-4">
                            <label className="block text-xs text-slate-400 font-mono uppercase tracking-wider mb-1">
                                Longitude
                            </label>
                            <input
                                type="number"
                                step="0.000001"
                                min="-180"
                                max="180"
                                placeholder="e.g. 75.781"
                                value={form.lon}
                                onChange={(e) => setForm((f) => ({ ...f, lon: e.target.value }))}
                                className="w-full bg-[#080f1a] border border-[#1e3a5f] rounded-md px-3 py-2.5 text-sm text-sky-300 font-mono focus:border-sky-400 focus:outline-none"
                            />
                        </div>

                        <div className="text-xs text-slate-500 mb-5">
                            Right-click any location on Google Maps, then copy coordinates.
                        </div>

                        <div className="text-xs font-mono text-sky-400 uppercase tracking-widest mb-4 pb-3 border-b border-[#1e3a5f]">
                            Step 2 - Analysis area size
                        </div>

                        <div className="grid grid-cols-3 gap-2 mb-5">
                            {["1", "2", "3"].map((s) => (
                                <button
                                    type="button"
                                    key={s}
                                    onClick={() => setForm((f) => ({ ...f, size: s }))}
                                    className={`min-h-14 px-2 rounded-md border text-xs font-mono transition-all ${
                                        form.size === s
                                            ? "border-sky-400 bg-sky-400/10 text-sky-300"
                                            : "border-[#1e3a5f] text-slate-400 hover:border-sky-400/50"
                                    }`}
                                >
                                    <span className="block">
                                        {s === "1" ? "Small" : s === "2" ? "Medium" : "Large"}
                                    </span>
                                    <span className="block text-[11px] opacity-80">
                                        {s === "1" ? "5x5 km" : s === "2" ? "10x10 km" : "20x20 km"}
                                    </span>
                                </button>
                            ))}
                        </div>

                        <div className="text-xs font-mono text-sky-400 uppercase tracking-widest mb-4 pb-3 border-b border-[#1e3a5f]">
                            Step 3 - Delivery
                        </div>

                        <div className="mb-4">
                            <label className="block text-xs text-slate-400 font-mono uppercase tracking-wider mb-1">
                                Scene Date
                            </label>
                            <input
                                type="date"
                                value={form.scene_date}
                                onChange={(e) => setForm((f) => ({ ...f, scene_date: e.target.value }))}
                                className="w-full bg-[#080f1a] border border-[#1e3a5f] rounded-md px-3 py-2.5 text-sm text-sky-300 font-mono focus:border-sky-400 focus:outline-none"
                            />
                        </div>

                        <div className="mb-6">
                            <label className="block text-xs text-slate-400 font-mono uppercase tracking-wider mb-1">
                                Email for Report Delivery
                            </label>
                            <input
                                type="email"
                                placeholder="your@email.com"
                                value={form.client_email}
                                onChange={(e) => setForm((f) => ({ ...f, client_email: e.target.value }))}
                                className="w-full bg-[#080f1a] border border-[#1e3a5f] rounded-md px-3 py-2.5 text-sm text-sky-300 font-mono focus:border-sky-400 focus:outline-none"
                            />
                        </div>

                        {step === "error" && (
                            <div className="mb-4 p-3 bg-red-900/20 border border-red-700 rounded-lg text-red-400 text-sm">
                                {error}
                            </div>
                        )}

                        <button
                            type="button"
                            onClick={handleSubmit}
                            className="w-full bg-sky-500 hover:bg-sky-400 text-white font-mono text-sm uppercase tracking-widest py-3 rounded-md transition-all"
                        >
                            Run Analysis
                        </button>
                    </>
                )}

                {step === "loading" && (
                    <div className="text-center py-8">
                        <div className="w-12 h-12 border-2 border-sky-400 border-t-transparent rounded-full animate-spin mx-auto mb-5" />
                        <div className="text-sky-400 font-mono text-sm mb-2">Triggering pipeline...</div>
                        <p className="text-slate-500 text-xs">
                            Contacting GitHub Actions to start the satellite analysis.
                        </p>
                    </div>
                )}

                {step === "done" && (
                    <div className="text-center py-4">
                        <div className="w-14 h-14 rounded-full bg-green-900/30 border border-green-700 flex items-center justify-center mx-auto mb-5">
                            <span className="text-2xl text-green-300">✓</span>
                        </div>
                        <div className="text-green-400 font-mono text-sm mb-3">Pipeline triggered!</div>
                        <p className="text-slate-400 text-sm mb-5 leading-relaxed">
                            Your satellite analysis has started. The full pipeline takes approximately{" "}
                            <strong className="text-white">15-25 minutes</strong> to complete. You will
                            receive an email at <span className="text-sky-400">{form.client_email}</span>{" "}
                            when it is ready.
                        </p>

                        {bbox && (
                            <div className="bg-[#080f1a] border border-[#1e3a5f] rounded-lg p-3 mb-5 text-left">
                                <div className="text-xs font-mono text-sky-400 uppercase tracking-wider mb-2">
                                    Analysis area
                                </div>
                                <div className="grid grid-cols-2 gap-1 text-xs font-mono">
                                    <span className="text-slate-500">SW</span>
                                    <span className="text-sky-300">{bbox.min_lat}, {bbox.min_lon}</span>
                                    <span className="text-slate-500">NE</span>
                                    <span className="text-sky-300">{bbox.max_lat}, {bbox.max_lon}</span>
                                    <span className="text-slate-500">Size</span>
                                    <span className="text-sky-300">{sizeLabels[form.size]}</span>
                                </div>
                            </div>
                        )}

                        <div className="text-xs text-slate-600 font-mono mb-5">
                            Job ID: {jobId}
                        </div>

                        <button
                            type="button"
                            onClick={() => {
                                setStep("form");
                                setForm((f) => ({ ...f, lat: "", lon: "" }));
                            }}
                            className="text-slate-400 hover:text-sky-400 text-sm font-mono transition-colors"
                        >
                            Run another analysis
                        </button>
                    </div>
                )}
            </div>

            <div className="mt-8 flex flex-wrap justify-center gap-4 text-xs text-slate-600 font-mono">
                {["ESA SENTINEL-2", "NASA GIBS", "SRTM DEM", "OPEN-METEO", "SOILGRIDS", "NOMINATIM"].map((s) => (
                    <span key={s}>{s}</span>
                ))}
            </div>
        </main>
    );
}
