'use client';
import { memo, Component, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  AreaChart, Area, LineChart, Line, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  LabelList
} from 'recharts';
import styles from './builder/MainContent.module.css';

// Extracted from MainContent.tsx so it can be reused by both the chat report
// cards and the public share page. Pure extraction — behavior is unchanged.

export const EXECUTIVE_COLORS = [
  '#2D2A26', // Deep Charcoal
  '#D4A843', // Warm StratAI Gold
  '#3B82F6', // Corporate Blue
  '#10B981', // Emerald
  '#8B5CF6', // Purple
  '#EC4899', // Rose
  '#F59E0B', // Amber
  '#06B6D4', // Cyan
  '#6366F1', // Indigo
];

export const resolveChartContext = (data: any, chartData: any[], chartType: string) => {
  const title = (data.title || '').trim();
  const lowerTitle = title.toLowerCase();

  // Detect scale types
  const isTenScale = lowerTitle.includes('1-10') || lowerTitle.includes('1–10') || lowerTitle.includes('index') || lowerTitle.includes('scale');
  const isPercentage = lowerTitle.includes('share') || lowerTitle.includes('%') || lowerTitle.includes('voice') || lowerTitle.includes('percent');

  // 1. Resolve X-Axis Demonstration
  let xLabel = data.x_label || '';
  if (!xLabel) {
    if (lowerTitle.includes('brand') || lowerTitle.includes('competitor') || lowerTitle.includes('pricing') || lowerTitle.includes('price') || lowerTitle.includes('scale signal')) {
      xLabel = 'Brands & Competitors Analyzed';
    } else if (lowerTitle.includes('channel') || lowerTitle.includes('acquisition') || lowerTitle.includes('media')) {
      xLabel = 'Marketing & Growth Channels';
    } else if (lowerTitle.includes('segment') || lowerTitle.includes('audience') || lowerTitle.includes('customer')) {
      xLabel = 'Target Customer Segments';
    } else if (lowerTitle.includes('timeline') || lowerTitle.includes('month') || lowerTitle.includes('quarter') || lowerTitle.includes('phase')) {
      xLabel = 'Execution Phase / Timeline';
    } else if (chartData.length > 0 && chartData[0].subject) {
      xLabel = 'Strategic Dimensions Evaluated';
    } else {
      xLabel = 'Analyzed Categories';
    }
  }

  // 2. Resolve Y-Axis Demonstration & Metric Units
  let yLabel = data.y_label || '';
  let yShortLabel = '';
  let metricUnit = data.unit || '';
  if (!yLabel) {
    if (lowerTitle.includes('price') || lowerTitle.includes('pricing')) {
      yLabel = 'Price Index (Scale 1–10: 1 = Budget, 10 = Luxury/Premium)';
      yShortLabel = 'Price Index (1–10)';
      metricUnit = 'Price Index';
    } else if (lowerTitle.includes('scale')) {
      yLabel = 'Scale Signal (1–10) • Digital Reach & Operational Volume (1 = Niche Challenger, 10 = Market Giant)';
      yShortLabel = 'Scale Signal (1–10)';
      metricUnit = 'Scale Score';
    } else if (isPercentage) {
      yLabel = 'Share of Voice (%) • Organic & Digital Market Presence';
      yShortLabel = 'Share (%)';
      metricUnit = 'Share (%)';
    } else if (lowerTitle.includes('budget') || lowerTitle.includes('spend') || lowerTitle.includes('allocation')) {
      yLabel = 'Budget Allocation Weight / Resource Focus';
      yShortLabel = 'Resource Weight';
      metricUnit = 'Allocation';
    } else if (lowerTitle.includes('intensity') || lowerTitle.includes('effort')) {
      yLabel = 'Execution Intensity (Scale 1–10)';
      yShortLabel = 'Intensity (1–10)';
      metricUnit = 'Intensity Score';
    } else {
      yLabel = 'Benchmark Performance Score';
      yShortLabel = 'Score';
      metricUnit = 'Score';
    }
  } else {
    yShortLabel = yLabel.includes('Scale Signal') ? 'Scale Signal (1–10)' : (yLabel.split('(')[0].trim() || yLabel);
  }

  // 3. Resolve Descriptive Meaning (What the graph actually measures)
  let description = data.description || '';
  if (!description) {
    if (lowerTitle.includes('price') || lowerTitle.includes('pricing')) {
      description = 'Benchmarks commercial pricing positioning relative to direct competitors. High scores reflect premium, high-margin brand positioning, whereas lower scores reflect accessibility, economy pricing, or freemium customer acquisition.';
    } else if (lowerTitle.includes('scale')) {
      description = 'Evaluates operational scale, content volume, and digital reach signals to compare institutional market weight against agile challenger brands.';
    } else if (isPercentage) {
      description = 'Measures estimated brand visibility, search prominence, and social conversation share across competitive alternatives.';
    } else if (lowerTitle.includes('budget') || lowerTitle.includes('allocation')) {
      description = 'Illustrates strategic capital and operational focus distribution across customer acquisition and brand awareness channels.';
    } else if (lowerTitle.includes('segment') || lowerTitle.includes('customer')) {
      description = 'Maps target audience distribution across core demographic and organizational buying groups.';
    } else if (chartType === 'radar') {
      description = 'Multi-dimensional competitive capability matrix highlighting differentiation boundaries, strengths, and market vulnerabilities.';
    } else {
      description = `Visual strategic benchmark evaluating ${xLabel.toLowerCase()} against ${yLabel.toLowerCase()}.`;
    }
  }

  // 4. Synthesize Strategic Meaning / Takeaway
  let takeaway = data.takeaway || '';
  if (!takeaway && Array.isArray(chartData) && chartData.length > 0) {
    const numericItems = chartData
      .filter((d: any) => typeof d.value === 'number')
      .sort((a: any, b: any) => b.value - a.value);

    if (numericItems.length >= 2) {
      const highest = numericItems[0];
      const lowest = numericItems[numericItems.length - 1];
      const sum = numericItems.reduce((acc: number, curr: any) => acc + curr.value, 0);
      const avg = (sum / numericItems.length).toFixed(1);

      if (lowerTitle.includes('price') || lowerTitle.includes('pricing')) {
        takeaway = `${highest.name} commands the highest price point (${highest.value}/10), establishing luxury or premium positioning. Conversely, ${lowest.name} (${lowest.value}/10) focuses on value-driven volume. The market benchmark median is ${avg}/10, indicating competitive pricing room for differentiated mid-to-high offerings.`;
      } else if (lowerTitle.includes('scale')) {
        takeaway = `${highest.name} leads in aggregate operational scale (${highest.value}/10), whereas ${lowest.name} (${lowest.value}/10) operates as a focused specialist. Peer group average sits at ${avg}/10.`;
      } else if (isPercentage) {
        takeaway = `${highest.name} dominates estimated share of voice (${highest.value}%), while the remaining segment is contested among challengers.`;
      } else {
        takeaway = `${highest.name} ranks highest with a score of ${highest.value}, compared to the benchmark baseline of ${lowest.value} held by ${lowest.name} (Peer average: ${avg}).`;
      }
    }
  }

  return { xLabel, yLabel, yShortLabel, metricUnit, description, takeaway, isTenScale, isPercentage };
};

export const CustomChartTooltip = ({ active, payload, label, context }: any) => {
  if (!active || !payload || !payload.length) return null;
  return (
    <div style={{
      background: '#FFFFFF',
      border: '1px solid #E8E4DC',
      borderRadius: '10px',
      padding: '10px 14px',
      boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.04)',
      fontSize: '12px',
      fontFamily: "'Inter', sans-serif",
      minWidth: '150px',
    }}>
      {label && (
        <div style={{ fontWeight: 700, color: '#1A1A1A', marginBottom: '6px', borderBottom: '1px solid #F0ECE4', paddingBottom: '4px' }}>
          {label}
        </div>
      )}
      {payload.map((item: any, i: number) => {
        let metricName = item.name;
        if (!metricName || metricName === 'value') {
          metricName = context?.metricUnit || 'Score';
        }

        let valText = `${item.value}`;
        if (context?.isTenScale && typeof item.value === 'number') {
          const tier = item.value >= 8 ? 'Premium' : item.value >= 5 ? 'Mid-Tier' : 'Budget';
          valText = `${item.value} / 10 (${tier})`;
        } else if (context?.isPercentage && typeof item.value === 'number') {
          valText = `${item.value}%`;
        }

        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '14px', marginTop: '4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: item.color || item.fill }} />
              <span style={{ color: '#57534E', fontWeight: 500 }}>{metricName}</span>
            </div>
            <span style={{ fontWeight: 700, color: '#1A1A1A' }}>{valText}</span>
          </div>
        );
      })}
    </div>
  );
};

// Small, visually-consistent fallback shown whenever a `recharts` block can't be
// trusted enough to render as a chart (malformed JSON, unsupported type, no data).
export const ChartFallbackCard = ({ message, rawContent }: { message: string; rawContent?: string }) => (
  <div style={{
    width: '100%',
    maxWidth: '100%',
    boxSizing: 'border-box',
    margin: '22px 0',
    background: '#FFFFFF',
    borderRadius: '16px',
    padding: '20px 24px',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
    border: '1px solid #E8E4DC',
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <div style={{
        background: '#FAF8F5',
        border: '1px solid #E8E4DC',
        width: 32,
        height: 32,
        borderRadius: '8px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        color: '#6B6560'
      }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 3v18h18" />
          <path d="M7 15l3-4 3 2 4-6" />
        </svg>
      </div>
      <span style={{ fontSize: '13px', fontWeight: 700, color: '#6B6560' }}>{message}</span>
    </div>
    {rawContent && (
      <details style={{ marginTop: '12px' }}>
        <summary style={{ fontSize: '11px', fontWeight: 600, color: '#A39E97', cursor: 'pointer' }}>
          Show raw block
        </summary>
        <pre style={{
          marginTop: '8px',
          fontSize: '11px',
          color: '#6B6560',
          background: '#FAF8F5',
          border: '1px solid #E8E4DC',
          borderRadius: '8px',
          padding: '10px',
          overflowX: 'auto',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          margin: '8px 0 0'
        }}>{rawContent}</pre>
      </details>
    )}
  </div>
);

// Error boundary around ONLY the live Recharts render — if Recharts itself throws
// during its own internal render (bad value type, scale error, etc.) this contains
// the crash to the one chart instead of taking down the whole page.
export class ChartErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: { componentStack?: string }) {
    console.error('[ChartErrorBoundary] Chart render failed:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          width: '100%',
          height: '100%',
          minHeight: 220,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#FAF8F5',
          border: '1px solid #E8E4DC',
          borderRadius: '12px',
          color: '#6B6560',
          fontSize: '13px',
          fontWeight: 600
        }}>
          Chart could not be rendered
        </div>
      );
    }
    return this.props.children;
  }
}

export const VALID_CHART_TYPES = ['bar', 'line', 'area', 'radar', 'pie'];

export const RechartsBlock = memo(({ children, className, ...props }: any) => {
  const rawText = String(children).replace(/\n$/, '');
  try {
    const data = JSON.parse(rawText);
    const COLORS = EXECUTIVE_COLORS;

    // Normalize chart type
    let chartType = (data.type || '').toString().toLowerCase().trim();
    if (chartType === 'bar_chart' || chartType === 'column') chartType = 'bar';
    if (chartType === 'line_chart' || chartType === 'trend') chartType = 'line';
    if (chartType === 'area_chart') chartType = 'area';
    if (chartType === 'radar_chart' || chartType === 'spider') chartType = 'radar';
    if (chartType === 'pie_chart' || chartType === 'donut') chartType = 'pie';

    // Auto-detect missing chart type based on data structure
    const chartData = Array.isArray(data.data) ? data.data : [];
    if (!chartType) {
      const sampleItem = chartData[0] || {};
      if ('subject' in sampleItem) {
        chartType = 'radar';
      } else if (data.keys && data.keys.length > 0) {
        chartType = 'line';
      } else {
        chartType = 'bar';
      }
    }

    // Unknown/unsupported type (typo, future type, etc.) — do NOT fall through to
    // a PieChart render that doesn't match the data. Show a clear fallback instead.
    if (!VALID_CHART_TYPES.includes(chartType)) {
      return <ChartFallbackCard message="Unsupported chart type" rawContent={rawText} />;
    }

    // No usable data — show an explicit empty state instead of a blank axes shell.
    if (chartData.length === 0) {
      return <ChartFallbackCard message="No chart data available" rawContent={rawText} />;
    }

    const keys = data.keys || (chartData.length > 0 ? Object.keys(chartData[0]).filter(k => k !== 'name' && k !== 'subject' && k !== 'category') : ['value']);
    const effectiveKeys = keys.length > 0 ? keys : ['value'];

    // Resolve comprehensive axis demonstration, descriptions, and takeaways
    const context = resolveChartContext(data, chartData, chartType);

    // Compute executive summary stat badges for fullness and immediate insight
    const kpiSummary = (() => {
      if (!Array.isArray(chartData) || chartData.length === 0) return null;
      const numItems = chartData
        .map((d: any) => {
          const key0 = effectiveKeys[0];
          const val = typeof d[key0] === 'number' 
            ? d[key0] 
            : (typeof d.value === 'number' ? d.value : null);
          return {
            name: d.name || d.subject || d.category || 'Entity',
            val
          };
        })
        .filter((d: any) => d.val !== null);

      if (numItems.length === 0) return null;

      const sorted = [...numItems].sort((a, b) => b.val - a.val);
      const highest = sorted[0];
      const lowest = sorted[sorted.length - 1];
      const sum = sorted.reduce((acc, curr) => acc + curr.val, 0);
      const avg = (sum / sorted.length).toFixed(1);
      const unit = context.isPercentage ? '%' : (context.isTenScale ? ' / 10' : '');

      return {
        leader: highest ? { name: highest.name, val: `${highest.val}${unit}` } : null,
        average: `${avg}${unit}`,
        baseline: lowest && lowest.name !== highest?.name ? { name: lowest.name, val: `${lowest.val}${unit}` } : null,
        count: `${chartData.length} Entities Benchmarked`,
      };
    })();

    return (
      <div style={{
        width: '100%',
        maxWidth: '100%',
        boxSizing: 'border-box',
        margin: '22px 0',
        background: '#FFFFFF',
        borderRadius: '16px',
        padding: '24px 26px',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
        border: '1px solid #E8E4DC',
        overflow: 'hidden'
      }}>
        {/* Card Header with Title and Descriptive Subtitle */}
        <div style={{ marginBottom: '16px', borderBottom: '1px solid #F0ECE4', paddingBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <div style={{ 
                background: '#FAF5EC', 
                border: '1px solid rgba(212, 168, 67, 0.3)', 
                padding: '3px 9px', 
                borderRadius: '6px', 
                fontSize: '10px', 
                fontWeight: 800, 
                letterSpacing: '0.06em', 
                color: '#B45309' 
              }}>
                EXECUTIVE VISUAL &bull; {chartType.toUpperCase()}
              </div>
              {data.title && <span style={{ fontSize: '15px', fontWeight: 700, color: '#1A1A1A', letterSpacing: '-0.01em' }}>{data.title}</span>}
            </div>
          </div>
          {context.description && (
            <p style={{ margin: 0, fontSize: '12.5px', color: '#6B6560', lineHeight: 1.55 }}>
              {context.description}
            </p>
          )}
        </div>

        {/* Clear Axis Demonstration Guide with High-Contrast Bold demonstration */}
        {chartType !== 'pie' && chartType !== 'radar' && (
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            marginBottom: '16px',
            background: '#FAF7F2',
            border: '1px solid #EAE3D5',
            borderRadius: '10px',
            padding: '10px 14px',
            fontSize: '12px',
            boxSizing: 'border-box',
            width: '100%',
            maxWidth: '100%'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span style={{ 
                fontWeight: 800, 
                color: '#B45309', 
                background: '#F5EFE3', 
                border: '1px solid rgba(180, 83, 9, 0.25)', 
                padding: '3px 8px', 
                borderRadius: '5px', 
                fontSize: '10px', 
                letterSpacing: '0.04em' 
              }}>
                HORIZONTAL (X-AXIS)
              </span>
              <span style={{ fontWeight: 700, color: '#1A1A1A', fontSize: '13px' }}>
                {context.xLabel}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span style={{ 
                fontWeight: 800, 
                color: '#FFFFFF', 
                background: '#1A1A1A', 
                padding: '3px 8px', 
                borderRadius: '5px', 
                fontSize: '10px', 
                letterSpacing: '0.04em' 
              }}>
                VERTICAL (Y-AXIS)
              </span>
              <span style={{ 
                fontWeight: 800, 
                color: '#0F0E0D', 
                fontSize: '13px', 
                background: '#FFF8E6', 
                padding: '3px 10px', 
                borderRadius: '6px', 
                border: '1.5px solid #D4A843' 
              }}>
                {context.yLabel}
              </span>
            </div>
          </div>
        )}

        {/* Executive Summary Stat Badges to visually fill space */}
        {kpiSummary && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: '10px',
            marginBottom: '18px',
            width: '100%',
            maxWidth: '100%',
            boxSizing: 'border-box'
          }}>
            {kpiSummary.leader && (
              <div style={{
                background: 'linear-gradient(135deg, #FAF7F2, #F5EEE1)',
                border: '1px solid #E5DCCB',
                borderRadius: '8px',
                padding: '8px 12px',
                boxSizing: 'border-box'
              }}>
                <div style={{ fontSize: '10px', fontWeight: 800, color: '#B45309', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  ★ PEAK BENCHMARK
                </div>
                <div style={{ fontSize: '13px', fontWeight: 800, color: '#1A1A1A', marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={kpiSummary.leader.name}>
                  {kpiSummary.leader.name}: <span style={{ color: '#B45309' }}>{kpiSummary.leader.val}</span>
                </div>
              </div>
            )}
            <div style={{
              background: '#FAF8F5',
              border: '1px solid #ECE7DE',
              borderRadius: '8px',
              padding: '8px 12px',
              boxSizing: 'border-box'
            }}>
              <div style={{ fontSize: '10px', fontWeight: 800, color: '#57534E', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                MARKET AVERAGE
              </div>
              <div style={{ fontSize: '13px', fontWeight: 800, color: '#1A1A1A', marginTop: '2px' }}>
                {kpiSummary.average}
              </div>
            </div>
            {kpiSummary.baseline && (
              <div style={{
                background: '#FAF8F5',
                border: '1px solid #ECE7DE',
                borderRadius: '8px',
                padding: '8px 12px',
                boxSizing: 'border-box'
              }}>
                <div style={{ fontSize: '10px', fontWeight: 800, color: '#57534E', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  FOCUSED BASELINE
                </div>
                <div style={{ fontSize: '13px', fontWeight: 800, color: '#1A1A1A', marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={kpiSummary.baseline.name}>
                  {kpiSummary.baseline.name}: {kpiSummary.baseline.val}
                </div>
              </div>
            )}
            <div style={{
              background: '#FAF8F5',
              border: '1px solid #ECE7DE',
              borderRadius: '8px',
              padding: '8px 12px',
              boxSizing: 'border-box'
            }}>
              <div style={{ fontSize: '10px', fontWeight: 800, color: '#57534E', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                PEER COVERAGE
              </div>
              <div style={{ fontSize: '13px', fontWeight: 800, color: '#1A1A1A', marginTop: '2px' }}>
                {kpiSummary.count}
              </div>
            </div>
          </div>
        )}

        <div style={{ width: '100%', maxWidth: '100%', height: 350, boxSizing: 'border-box', overflow: 'hidden', position: 'relative' }}>
        <ChartErrorBoundary>
        <ResponsiveContainer width="100%" height="100%">
          {chartType === 'line' ? (
            <LineChart data={chartData} margin={{ top: 22, right: 30, left: 25, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EFECE6" />
              <XAxis 
                dataKey="name" 
                stroke="#8C857B"
                tickLine={false}
                axisLine={{ stroke: '#E8E4DC' }}
                tick={{ fill: '#1A1A1A', fontSize: 11.5, fontWeight: 600 }} 
              />
              <YAxis 
                stroke="#8C857B" 
                tickLine={false} 
                axisLine={false} 
                tick={{ fill: '#1A1A1A', fontSize: 12, fontWeight: 700 }}
                label={{ 
                  value: context.yShortLabel, 
                  angle: -90, 
                  position: 'insideLeft', 
                  offset: 2, 
                  fill: '#1A1A1A', 
                  fontSize: 12.5, 
                  fontWeight: 800,
                  style: { textAnchor: 'middle', fontWeight: 800, fill: '#1A1A1A' }
                }}
              />
              <Tooltip content={<CustomChartTooltip context={context} />} />
              {effectiveKeys.length > 1 && (
                <Legend wrapperStyle={{ paddingTop: 14, fontSize: 12, fontWeight: 600 }} iconType="circle" iconSize={9} />
              )}
              {effectiveKeys.map((key: string, idx: number) => (
                <Line 
                  key={key} 
                  type="monotone" 
                  dataKey={key} 
                  stroke={COLORS[idx % COLORS.length]} 
                  strokeWidth={3} 
                  dot={{ r: 4.5, fill: '#FFFFFF', stroke: COLORS[idx % COLORS.length], strokeWidth: 2.5 }} 
                  activeDot={{ r: 7, fill: COLORS[idx % COLORS.length], stroke: '#FFFFFF', strokeWidth: 2.5 }}
                >
                  <LabelList dataKey={key} position="top" fill="#1A1A1A" fontSize={11} fontWeight={700} offset={8} />
                </Line>
              ))}
            </LineChart>
          ) : chartType === 'area' ? (
            <AreaChart data={chartData} margin={{ top: 22, right: 30, left: 25, bottom: 40 }}>
              <defs>
                {effectiveKeys.map((key: string, idx: number) => {
                  const col = COLORS[idx % COLORS.length];
                  return (
                    <linearGradient key={`grad-${key}`} id={`grad-${key}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={col} stopOpacity={0.35} />
                      <stop offset="95%" stopColor={col} stopOpacity={0.03} />
                    </linearGradient>
                  );
                })}
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EFECE6" />
              <XAxis 
                dataKey="name" 
                stroke="#8C857B"
                tickLine={false}
                axisLine={{ stroke: '#E8E4DC' }}
                tick={{ fill: '#1A1A1A', fontSize: 11.5, fontWeight: 600 }} 
              />
              <YAxis 
                stroke="#8C857B" 
                tickLine={false} 
                axisLine={false} 
                tick={{ fill: '#1A1A1A', fontSize: 12, fontWeight: 700 }}
                label={{ 
                  value: context.yShortLabel, 
                  angle: -90, 
                  position: 'insideLeft', 
                  offset: 2, 
                  fill: '#1A1A1A', 
                  fontSize: 12.5, 
                  fontWeight: 800,
                  style: { textAnchor: 'middle', fontWeight: 800, fill: '#1A1A1A' }
                }}
              />
              <Tooltip content={<CustomChartTooltip context={context} />} />
              {effectiveKeys.length > 1 && (
                <Legend wrapperStyle={{ paddingTop: 14, fontSize: 12, fontWeight: 600 }} iconType="circle" iconSize={9} />
              )}
              {effectiveKeys.map((key: string, idx: number) => (
                <Area 
                  key={key} 
                  type="monotone" 
                  dataKey={key} 
                  stroke={COLORS[idx % COLORS.length]} 
                  strokeWidth={3}
                  fill={`url(#grad-${key})`} 
                />
              ))}
            </AreaChart>
          ) : chartType === 'radar' ? (
            <RadarChart cx="50%" cy="50%" outerRadius="75%" data={chartData}>
              <PolarGrid stroke="#E8E4DC" />
              <PolarAngleAxis 
                dataKey={chartData[0]?.subject !== undefined ? "subject" : (chartData[0]?.name !== undefined ? "name" : "category")} 
                tick={{ fill: '#1A1A1A', fontSize: 11.5, fontWeight: 700 }} 
              />
              <PolarRadiusAxis angle={30} domain={[0, 10]} stroke="#D4A843" tick={{ fill: '#57534E', fontSize: 10, fontWeight: 600 }} />
              <Tooltip content={<CustomChartTooltip context={context} />} />
              {effectiveKeys.length > 1 && (
                <Legend wrapperStyle={{ paddingTop: 14, fontSize: 12, fontWeight: 600 }} iconType="circle" iconSize={9} />
              )}
              {effectiveKeys.map((key: string, idx: number) => (
                <Radar 
                  key={key} 
                  name={key} 
                  dataKey={key} 
                  stroke={COLORS[idx % COLORS.length]} 
                  strokeWidth={2.5}
                  fill={COLORS[idx % COLORS.length]} 
                  fillOpacity={0.35} 
                />
              ))}
            </RadarChart>
          ) : chartType === 'bar' ? (
            <BarChart 
              data={chartData} 
              layout={data.layout || 'horizontal'} 
              margin={data.layout === 'vertical' 
                ? { top: 12, right: 30, left: 15, bottom: 12 }
                : { top: 24, right: 25, left: 25, bottom: 45 }
              }
              barCategoryGap="16%"
              barGap={6}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EFECE6" />
              {data.layout === 'vertical' ? (
                <>
                  <XAxis type="number" stroke="#8C857B" tick={{ fill: '#1A1A1A', fontSize: 12, fontWeight: 700 }} tickLine={false} axisLine={{ stroke: '#E8E4DC' }} />
                  <YAxis 
                    dataKey="name" 
                    type="category" 
                    width={130} 
                    stroke="#8C857B"
                    tickLine={false}
                    axisLine={{ stroke: '#E8E4DC' }}
                    tick={({ x, y, payload }: any) => {
                      const text = payload.value || '';
                      const display = text.length > 20 ? `${text.slice(0, 19)}…` : text;
                      return (
                        <text x={x} y={y} dy={4} textAnchor="end" fill="#1A1A1A" fontSize={11.5} fontWeight={600}>
                          {display}
                        </text>
                      );
                    }}
                  />
                </>
              ) : (
                <>
                  <XAxis 
                    dataKey="name" 
                    stroke="#8C857B"
                    interval={0} 
                    tickLine={false}
                    axisLine={{ stroke: '#E8E4DC' }}
                    tick={({ x, y, payload }: any) => {
                      const text = payload.value || '';
                      const isLong = text.length > 16;
                      const display = isLong ? `${text.slice(0, 15)}…` : text;
                      return (
                        <text x={x} y={y + 12} textAnchor="end" transform={`rotate(-18 ${x} ${y + 12})`} fill="#1A1A1A" fontSize={11.5} fontWeight={600}>
                          {display}
                        </text>
                      );
                    }}
                  />
                  <YAxis 
                    stroke="#8C857B" 
                    tickLine={false} 
                    axisLine={false} 
                    tick={{ fill: '#1A1A1A', fontSize: 12, fontWeight: 700 }}
                    label={{ 
                      value: context.yShortLabel, 
                      angle: -90, 
                      position: 'insideLeft', 
                      offset: 2, 
                      fill: '#1A1A1A', 
                      fontSize: 12.5, 
                      fontWeight: 800,
                      style: { textAnchor: 'middle', fontWeight: 800, fill: '#1A1A1A' } 
                    }}
                  />
                </>
              )}
              <Tooltip content={<CustomChartTooltip context={context} />} cursor={{ fill: 'rgba(212, 168, 67, 0.06)', rx: 6 }} />
              {effectiveKeys.length > 1 && (
                <Legend 
                  wrapperStyle={{ paddingTop: 14, fontSize: 12, fontWeight: 600 }}
                  iconType="circle"
                  iconSize={9}
                />
              )}
              {effectiveKeys.map((key: string, idx: number) => (
                <Bar 
                  key={key} 
                  dataKey={key} 
                  fill={COLORS[idx % COLORS.length]} 
                  background={{ fill: '#F8F6F2', radius: 6 }}
                  radius={data.layout === 'vertical' ? [0, 6, 6, 0] : [6, 6, 0, 0]}
                  maxBarSize={data.layout === 'vertical' ? 26 : 52}
                >
                  <LabelList 
                    dataKey={key} 
                    position={data.layout === 'vertical' ? 'right' : 'top'} 
                    fill="#1A1A1A" 
                    fontSize={12} 
                    fontWeight={800} 
                    offset={8} 
                  />
                  {!data.keys && chartData.map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              ))}
            </BarChart>
          ) : (
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="46%"
                innerRadius={52}
                outerRadius={96}
                paddingAngle={3}
                cornerRadius={5}
                labelLine={false}
                label={({ name, percent }: any) => `${name} (${((percent || 0) * 100).toFixed(0)}%)`}
                dataKey={effectiveKeys[0] || 'value'}
              >
                {chartData.map((entry: any, index: number) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip content={<CustomChartTooltip context={context} />} />
              <Legend verticalAlign="bottom" height={36} iconType="circle" iconSize={9} wrapperStyle={{ fontSize: 12, fontWeight: 600, color: '#1A1A1A' }} />
            </PieChart>
          )}
        </ResponsiveContainer>
        </ChartErrorBoundary>
        </div>

        {/* Strategic Takeaway & Meaning Banner */}
        {context.takeaway && (
          <div style={{
            marginTop: '16px',
            padding: '12px 16px',
            background: 'linear-gradient(135deg, #FAF8F5, #F5F1EB)',
            border: '1px solid #E8E4DC',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '12px',
            width: '100%',
            maxWidth: '100%',
            boxSizing: 'border-box',
            overflow: 'hidden'
          }}>
            <div style={{
              marginTop: '2px',
              width: '22px',
              height: '22px',
              borderRadius: '6px',
              background: 'linear-gradient(135deg, #2D2A26, #D4A843)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              color: '#FFFFFF'
            }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
              </svg>
            </div>
            <div style={{ flex: 1, minWidth: 0, overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
              <div style={{ fontSize: '10px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#B45309', marginBottom: '3px' }}>
                STRATEGIC MEANING & EXECUTIVE TAKEAWAY
              </div>
              <div style={{ fontSize: '13px', color: '#1A1A1A', lineHeight: 1.55, fontWeight: 500, overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
                {context.takeaway}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  } catch (e) {
    return <ChartFallbackCard message="Chart could not be rendered" rawContent={rawText} />;
  }
});
RechartsBlock.displayName = 'RechartsBlock';

export const markdownComponents = {
  code: ({ node, inline, className, children, ...props }: any) => {
    const match = /language-(\w+)/.exec(className || '');
    if (!inline && match && match[1] === 'recharts') {
      return <RechartsBlock className={className} {...props}>{children}</RechartsBlock>;
    }
    return <code className={className} {...props}>{children}</code>;
  },
  table: ({ children, ...props }: any) => (
    <div className={styles.tableWrapper}>
      <table {...props}>{children}</table>
    </div>
  )
};

export default function ReportRenderer({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeRaw]}
      components={markdownComponents}
    >
      {content
        .replace(/\(\$\$\$\)/g, '(Premium Tier)')
        .replace(/\(\$\$\)/g, '(Mid-Tier)')
        .replace(/\(\$\)/g, '(Budget)')
        .replace(/\$\$\$/g, 'Premium Tier')
        .replace(/\$\$/g, 'Mid-Tier')
      }
    </ReactMarkdown>
  );
}
