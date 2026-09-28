/**
 * CandlestickChart.jsx — Real-time TradingView candlestick chart using lightweight-charts v5
 *
 * Visualises public Binance USD-M Futures klines (BTCUSDT, ETHUSDT, SOLUSDT).
 * Supports public WebSocket live candle updates and backend /api/state klines.
 * Zero Math.random(). Real public market data only.
 *
 * PAPER / RESEARCH ONLY — No live orders.
 */

import { useEffect, useRef } from 'react'
import { createChart, CandlestickSeries } from 'lightweight-charts'

const CHART_THEME = {
  bg: '#181A20',
  grid: 'rgba(43, 49, 57, 0.45)',
  border: '#2B3139',
  text: '#848E9C',
  crosshair: '#707A8A',
  upColor: '#0ECB81',
  downColor: '#F6465D',
}

const parseBarTime = (t) => {
  if (typeof t === 'number') return t
  if (typeof t === 'string') {
    const ms = Date.parse(t)
    if (!Number.isNaN(ms)) return Math.floor(ms / 1000)
  }
  return Math.floor(Date.now() / 1000)
}

/**
 * @param {{
 *   symbol: string,
 *   timeframe?: string,
 *   candles: { time?: number, time_utc?: string, open: number, high: number, low: number, close: number, provisional?: boolean }[],
 *   precision?: number,
 *   liveCandle?: { time?: number, time_utc?: string, open: number, high: number, low: number, close: number } | null,
 *   status?: 'LOADING' | 'READY' | 'ERROR' | 'UNAVAILABLE',
 *   errorMessage?: string | null,
 * }} props
 */
export function CandlestickChart({
  symbol,
  timeframe = '1m',
  candles = [],
  precision = 2,
  liveCandle = null,
  status = 'READY',
  errorMessage = null,
}) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)
  const lastTimeRef = useRef(null)

  // ── Initialize chart instance ──────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || typeof ResizeObserver === 'undefined') return undefined

    const container = containerRef.current
    const initialWidth = container.clientWidth || 800
    const initialHeight = container.clientHeight || 380

    const chart = createChart(container, {
      width: initialWidth,
      height: initialHeight,
      layout: {
        background: { color: CHART_THEME.bg },
        textColor: CHART_THEME.text,
        fontSize: 11,
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      },
      grid: {
        vertLines: { color: CHART_THEME.grid },
        horzLines: { color: CHART_THEME.grid },
      },
      rightPriceScale: {
        borderColor: CHART_THEME.border,
        scaleMargins: { top: 0.1, bottom: 0.1 },
        visible: true,
      },
      leftPriceScale: {
        visible: false,
      },
      timeScale: {
        borderColor: CHART_THEME.border,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 6,
        barSpacing: 8,
        minBarSpacing: 3,
      },
      crosshair: {
        mode: 1, // Normal magnet
        vertLine: {
          color: CHART_THEME.crosshair,
          width: 1,
          style: 3,
          labelBackgroundColor: '#2B3139',
        },
        horzLine: {
          color: CHART_THEME.crosshair,
          width: 1,
          style: 3,
          labelBackgroundColor: '#2B3139',
        },
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
        axisPressedMouseMove: true,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
      },
    })

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: CHART_THEME.upColor,
      downColor: CHART_THEME.downColor,
      borderUpColor: CHART_THEME.upColor,
      borderDownColor: CHART_THEME.downColor,
      wickUpColor: CHART_THEME.upColor,
      wickDownColor: CHART_THEME.downColor,
      priceFormat: {
        type: 'price',
        precision,
        minMove: precision === 3 ? 0.001 : 0.01,
      },
    })

    chartRef.current = chart
    seriesRef.current = candlestickSeries

    // Load initial candles if available
    if (candles && candles.length > 0) {
      try {
        const sorted = candles
          .map((c) => ({
            time: parseBarTime(c.time || c.time_utc),
            open: Number(c.open),
            high: Number(c.high),
            low: Number(c.low),
            close: Number(c.close),
          }))
          .filter((c, idx, arr) => idx === 0 || c.time > arr[idx - 1].time)

        if (sorted.length > 0) {
          candlestickSeries.setData(sorted)
          chart.timeScale().fitContent()
          lastTimeRef.current = sorted[sorted.length - 1].time
        }
      } catch (err) {
        console.warn('Initial chart setData error:', err)
      }
    }

    // Observer for responsive width/height
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect
        if (width > 0 && height > 0 && chartRef.current) {
          chartRef.current.applyOptions({ width, height })
        }
      }
    })
    ro.observe(container)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
      lastTimeRef.current = null
    }
  }, [symbol, timeframe, precision])

  // ── Sync candles array updates from backend ─────────────────────────────────
  useEffect(() => {
    if (!seriesRef.current) return

    if (!candles || candles.length === 0) {
      try {
        seriesRef.current.setData([])
        lastTimeRef.current = null
      } catch {}
      return
    }

    try {
      const sorted = candles
        .map((c) => ({
          time: parseBarTime(c.time || c.time_utc),
          open: Number(c.open),
          high: Number(c.high),
          low: Number(c.low),
          close: Number(c.close),
        }))
        .filter((c, idx, arr) => idx === 0 || c.time > arr[idx - 1].time)

      if (sorted.length > 0) {
        seriesRef.current.setData(sorted)
        chartRef.current?.timeScale().fitContent()
        lastTimeRef.current = sorted[sorted.length - 1].time
      } else {
        seriesRef.current.setData([])
        lastTimeRef.current = null
      }
    } catch {
      // Fallback
    }
  }, [candles])

  // ── Live WebSocket or polling tick update ───────────────────────────────────
  useEffect(() => {
    if (!seriesRef.current || !liveCandle) return

    try {
      const barTime = parseBarTime(liveCandle.time || liveCandle.time_utc)
      seriesRef.current.update({
        time: barTime,
        open: Number(liveCandle.open),
        high: Number(liveCandle.high),
        low: Number(liveCandle.low),
        close: Number(liveCandle.close),
      })
      lastTimeRef.current = barTime
    } catch {
      // Silently ignore minor ordering hiccups during stream reconnect
    }
  }, [liveCandle])

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        position: 'absolute',
        inset: 0,
      }}
    >
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
          position: 'absolute',
          inset: 0,
        }}
        role="img"
        aria-label={`Biểu đồ nến ${symbol} (${timeframe}) — Dữ liệu công khai Binance USD-M Futures`}
      />
      {status === 'LOADING' && (
        <div className="chart-status-overlay" role="status" aria-live="polite">
          <div className="chart-spinner" aria-hidden="true" />
          <span>Đang tải nến {symbol} ({timeframe})...</span>
        </div>
      )}
      {(status === 'ERROR' || status === 'UNAVAILABLE') && (
        <div className="chart-status-overlay error" role="alert">
          <span>⚠ {errorMessage || 'Nguồn dữ liệu không sẵn sàng'}</span>
        </div>
      )}
      {status === 'READY' && (!candles || candles.length === 0) && (
        <div className="chart-status-overlay" role="status">
          <span>Chưa có dữ liệu nến cho {symbol} ({timeframe})</span>
        </div>
      )}
    </div>
  )
}
