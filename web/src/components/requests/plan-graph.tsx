import { useMemo, useState } from "react";
import { AlertTriangle, Maximize2, Minus, Plus } from "lucide-react";
import type { GraphNode, StepGraph } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { cn, humanize } from "@/lib/utils";

const phaseX: Record<string, number> = {
  FINDING: 30,
  REMEDIATION: 330,
  VERIFICATION: 630,
};

const phaseTone: Record<string, { fill: string; stroke: string; text: string }> = {
  FINDING: { fill: "#fb71851a", stroke: "#fb7185", text: "#fda4af" },
  REMEDIATION: { fill: "#fbbf241a", stroke: "#fbbf24", text: "#fcd34d" },
  VERIFICATION: { fill: "#34d3991a", stroke: "#34d399", text: "#6ee7b7" },
};

const NODE_WIDTH = 250;
const NODE_HEIGHT = 60;
const ROW_GAP = 78;

function nodePosition(node: GraphNode, indexInPhase: number) {
  return {
    x: phaseX[node.phase] ?? 30,
    y: 54 + indexInPhase * ROW_GAP,
  };
}

function shortResource(resource: string) {
  return resource.length > 31 ? `${resource.slice(0, 30)}…` : resource;
}

export function PlanGraph({ graph }: { graph: StepGraph }) {
  const [zoom, setZoom] = useState(0.85);
  const [expanded, setExpanded] = useState(false);

  const placement = useMemo(() => {
    const groups: Record<string, GraphNode[]> = {
      FINDING: [],
      REMEDIATION: [],
      VERIFICATION: [],
    };
    for (const node of graph.nodes) {
      (groups[node.phase] ??= []).push(node);
    }
    const positions = new Map<string, { x: number; y: number; node: GraphNode }>();
    for (const [phase, nodes] of Object.entries(groups)) {
      nodes.forEach((node, index) => {
        positions.set(node.id, { ...nodePosition(node, index), node, phase } as { x: number; y: number; node: GraphNode });
      });
    }
    const maxRows = Math.max(1, ...Object.values(groups).map((nodes) => nodes.length));
    const height = 86 + maxRows * ROW_GAP;
    return { positions, groups, height, width: 910 };
  }, [graph.nodes]);

  if (!graph.nodes.length) {
    return (
      <div className="flex min-h-40 items-center justify-center rounded-2xl border border-dashed border-border/70 text-sm text-muted-foreground">
        No plan graph is available for this request yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-3 text-[10px] uppercase tracking-widest text-muted-foreground">
          {Object.entries(phaseTone).map(([phase, tone]) => (
            <span key={phase} className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: tone.stroke }} />
              {humanize(phase)}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setZoom((value) => Math.max(0.45, value - 0.1))}
            aria-label="Zoom out"
          >
            <Minus className="h-3.5 w-3.5" />
          </Button>
          <span className="w-10 text-center font-mono text-[10px] text-muted-foreground">
            {Math.round(zoom * 100)}%
          </span>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setZoom((value) => Math.min(1.3, value + 0.1))}
            aria-label="Zoom in"
          >
            <Plus className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setExpanded((value) => !value)}
            aria-label={expanded ? "Exit fullscreen graph" : "Expand graph"}
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {graph.cycle ? (
        <div className="flex items-center gap-2 rounded-xl border border-rose-400/20 bg-rose-400/5 px-3 py-2 text-xs text-rose-300">
          <AlertTriangle className="h-4 w-4" /> A dependency cycle was detected. The plan is not executable.
        </div>
      ) : null}

      <div
        className={cn(
          "overflow-auto rounded-2xl border border-border/60 bg-[#071017]/60",
          expanded ? "max-h-[75vh]" : "max-h-[560px]",
        )}
      >
        <svg
          width={placement.width * zoom}
          height={placement.height * zoom}
          viewBox={`0 0 ${placement.width} ${placement.height}`}
          role="img"
          aria-label="Deletion plan dependency graph"
        >
          <defs>
            <marker id="graph-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#475569" />
            </marker>
          </defs>

          {Object.keys(phaseTone).map((phase) => (
            <text
              key={phase}
              x={(phaseX[phase] ?? 0) + NODE_WIDTH / 2}
              y={24}
              textAnchor="middle"
              fill="#64748b"
              fontSize={10}
              fontFamily="JetBrains Mono, monospace"
              letterSpacing={1.6}
            >
              {phase}
            </text>
          ))}

          {graph.edges.map(([from, to]) => {
            const source = placement.positions.get(from);
            const target = placement.positions.get(to);
            if (!source || !target) return null;
            const startsForward = target.x >= source.x;
            const x1 = startsForward ? source.x + NODE_WIDTH : source.x;
            const y1 = source.y + NODE_HEIGHT / 2;
            const x2 = startsForward ? target.x : target.x + NODE_WIDTH;
            const y2 = target.y + NODE_HEIGHT / 2;
            const bend = Math.max(30, Math.abs(x2 - x1) * 0.35);
            const c1 = startsForward ? x1 + bend : x1 - bend;
            const c2 = startsForward ? x2 - bend : x2 + bend;
            return (
              <path
                key={`${from}-${to}`}
                d={`M ${x1} ${y1} C ${c1} ${y1}, ${c2} ${y2}, ${x2} ${y2}`}
                fill="none"
                stroke="#475569"
                strokeWidth={1.1}
                markerEnd="url(#graph-arrow)"
                opacity={0.8}
              />
            );
          })}

          {Array.from(placement.positions.values()).map(({ x, y, node }) => {
            const tone = phaseTone[node.phase] ?? phaseTone.FINDING;
            return (
              <g key={node.id}>
                <title>
                  {node.operation} · {node.system_id}/{node.resource_id}
                </title>
                <rect
                  x={x}
                  y={y}
                  width={NODE_WIDTH}
                  height={NODE_HEIGHT}
                  rx={10}
                  fill={tone.fill}
                  stroke={tone.stroke}
                  strokeOpacity={0.45}
                />
                <circle cx={x + 14} cy={y + 17} r={3} fill={tone.stroke} />
                <text
                  x={x + 24}
                  y={y + 21}
                  fill={tone.text}
                  fontSize={9}
                  fontFamily="JetBrains Mono, monospace"
                  letterSpacing={0.8}
                >
                  {String(node.step_no).padStart(2, "0")} · {node.operation}
                </text>
                <text x={x + 14} y={y + 40} fill="#e2e8f0" fontSize={10.5} fontFamily="Manrope Variable, sans-serif">
                  {shortResource(node.resource_id)}
                </text>
                <text x={x + 14} y={y + 53} fill="#64748b" fontSize={8.5} fontFamily="JetBrains Mono, monospace">
                  {node.system_id}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[10px] text-muted-foreground">
        <span>{graph.nodes.length} steps</span>
        <span>{graph.edges.length} dependencies</span>
        <span>{graph.cycle ? "Cycle detected" : "DAG valid"}</span>
        {graph.critical_path.length ? (
          <span>Critical path: {graph.critical_path.length} steps</span>
        ) : null}
      </div>
    </div>
  );
}
