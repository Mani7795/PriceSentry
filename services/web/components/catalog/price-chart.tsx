"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from "recharts";
import type { PricePoint } from "@/lib/types";
import { retailerLabel } from "@/lib/format";

const RETAILER_COLORS: Record<string, string> = {
  amazon: "#FF9900",
  petbarn: "#E55934",
  petzoo: "#7C3AED",
  vetproductsdirect: "#0D9488",
  demo: "#64748b",
};

// Transform [{observed_at, competitor, price_cents}] into
// [{date, amazon, chewy, petco, petsmart}] for a multi-line chart.
function pivot(history: PricePoint[]) {
  const byDate: Record<string, Record<string, number | string>> = {};
  const retailers = new Set<string>();
  for (const p of history) {
    const date = p.observed_at.slice(0, 10);
    retailers.add(p.competitor);
    byDate[date] = byDate[date] || { date };
    byDate[date][p.competitor] = +(p.price_cents / 100).toFixed(2);
  }
  const rows = Object.values(byDate).sort((a, b) =>
    String(a.date).localeCompare(String(b.date))
  );
  return { rows, retailers: Array.from(retailers) };
}

export function PriceChart({ history }: { history: PricePoint[] }) {
  const { rows, retailers } = useMemo(() => pivot(history), [history]);

  if (rows.length === 0) {
    return (
      <div className="h-72 grid place-items-center text-sm text-muted">
        No price history available.
      </div>
    );
  }

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--color-border))" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: "rgb(var(--color-muted))" }}
            tickFormatter={(d) => String(d).slice(5)}
            minTickGap={32}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "rgb(var(--color-muted))" }}
            tickFormatter={(v) => `$${v}`}
            width={48}
          />
          <Tooltip
            contentStyle={{
              background: "rgb(var(--color-surface))",
              border: "1px solid rgb(var(--color-border))",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value: any, name: any) => [`$${value}`, retailerLabel(String(name))]}
          />
          <Legend formatter={(value) => retailerLabel(String(value))} wrapperStyle={{ fontSize: 12 }} />
          {retailers.map((r) => (
            <Line
              key={r}
              type="monotone"
              dataKey={r}
              stroke={RETAILER_COLORS[r] || "#64748b"}
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
