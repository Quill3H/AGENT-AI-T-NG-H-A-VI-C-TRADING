/**
 * CandlestickChart.jsx — TradingView-style candlestick chart using lightweight-charts v5
 *
 * Designed to look and feel like Binance Futures (BTCUSDT, ETHUSDT, SOLUSDT).
 * Smoothly re-initialises on coin change and updates in real-time with incoming ticks.
 *
 * PAPER / RESEARCH — Simulated price feeds, no live exchange orders.
 */

import { useEffect, useRef } from 'react'
import { createChart, CandlestickSeries } from 'lightweight-charts'

const CHART_THEME = {
  bg: '#181A20',
  grid: 'rgba(43, 49, 57, 0.5)',
  border: '#2B3139',
  text: '#848E9C',
  crosshair: '#707A8A',
  upColor: '#0ECB81',
  downColor: '#F6465D',
}

/**
 * @param {{
 *   symbol: string,
 *   candles: { time: number, open: number, high: number, low: number, close: number }[],
 *   precision?: number,
 * }} props
 */
export function CandlestickChart({ symbol, candles, precision = 2 }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)
  const lastTimeRef = useRef(null)

  useEffect(() => {
    // In headless / jsdom test environments, ResizeObserver may not exist
    if (!containerRef.current || typeof ResizeObserver === 'undefined') return undefined

    const container = containerRef.current
    const initialWidth = container.clientWidth || 800
    const initialHeight = container.clientHeight || 360

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
        minBarSpacing: 4,
      },
      crosshair: {
        mode: 1, // Magnet
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

    // Load initial data
    if (candles && candles.length > 0) {
      try {
        candlestickSeries.setData(candles)
        chart.timeScale().fitContent()
        lastTimeRef.current = candles[candles.length - 1].time
      } catch (err) {
        console.warn('Initial chart setData error:', err)
      }
    }

    // Responsive resize
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
  }, [symbol, precision]) // Re-run whenever symbol changes

  // Update latest candle on price tick
  useEffect(() => {
    if (!seriesRef.current || !candles || candles.length === 0) return
    const last = candles[candles.length - 1]
    if (!last) return

    try {
      // If time matches or is after the last candle, update
      seriesRef.current.update(last)
      lastTimeRef.current = last.time
    } catch {
      // If updating fails (e.g. sequence re-ordered), re-set all data
      try {
        seriesRef.current.setData(candles)
      } catch {
        // Ignore fallback error
      }
    }
  }, [candles])

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '100%',
        position: 'absolute',
        inset: 0,
      }}
      role="img"
      aria-label={`Biểu đồ nến ${symbol} — dữ liệu mô phỏng PAPER`}
    />
  )
}
