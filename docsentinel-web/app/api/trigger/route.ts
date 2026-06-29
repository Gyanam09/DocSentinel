import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const min_lat = Number(body.min_lat);
        const max_lat = Number(body.max_lat);
        const min_lon = Number(body.min_lon);
        const max_lon = Number(body.max_lon);
        const scene_date = String(body.scene_date || "2026-05-28");
        const client_email = String(body.client_email || "").trim();

        if (![min_lat, max_lat, min_lon, max_lon].every(Number.isFinite)) {
            return NextResponse.json({ error: "Coordinates must be valid numbers" }, { status: 400 });
        }
        if (min_lat < -90 || max_lat > 90 || min_lat >= max_lat) {
            return NextResponse.json({ error: "Latitude bounds are invalid" }, { status: 400 });
        }
        if (min_lon < -180 || max_lon > 180 || min_lon >= max_lon) {
            return NextResponse.json({ error: "Longitude bounds are invalid" }, { status: 400 });
        }
        if (!client_email || !client_email.includes("@")) {
            return NextResponse.json({ error: "Invalid email" }, { status: 400 });
        }

        const GITHUB_TOKEN = process.env.GITHUB_PAT;
        const REPO = process.env.GITHUB_REPO;

        if (!GITHUB_TOKEN || !REPO) {
            return NextResponse.json(
                { error: "GitHub integration not configured on server" },
                { status: 500 }
            );
        }

        const job_id = `ds-${Date.now()}`;

        const ghRes = await fetch(
            `https://api.github.com/repos/${REPO}/dispatches`,
            {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${GITHUB_TOKEN}`,
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                body: JSON.stringify({
                    event_type: "run_pipeline",
                    client_payload: {
                        min_lat, max_lat, min_lon, max_lon,
                        scene_date,
                        client_email,
                        job_id,
                    },
                }),
            }
        );

        if (!ghRes.ok) {
            const err = await ghRes.text();
            console.error("GitHub dispatch error:", err);
            return NextResponse.json(
                { error: `GitHub dispatch failed: ${ghRes.status}` },
                { status: 500 }
            );
        }

        return NextResponse.json({ job_id, status: "triggered" });

    } catch (err: unknown) {
        console.error("API error:", err);
        const message = err instanceof Error ? err.message : "Unknown server error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
}
