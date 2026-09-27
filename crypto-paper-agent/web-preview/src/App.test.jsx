import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { App } from './App'
import { buildOfflineReplay, parseEquityArtifact } from './lib/replay'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import previewEquityCsv from './data/long_equity_curve.csv?raw'
import foldReport from './data/walk_forward.report.json'
import publicManifest from './data/public_dataset_manifest.json'
import artifactAudit from './data/artifact_audit.json'
import { evidence } from './data/evidence'

const brokerEquityCsv = readFileSync(resolve(process.cwd(), '../docs/reviews/evidence/g0-2c9a4d0/replay/LONG/equity_curve.csv'), 'utf8')

describe('paper research console — Binance dark UI', () => {
  it('renders PAPER/RESEARCH safety labels and mode indicators', () => {
    render(<App />)
    // Safety banner
    expect(screen.getAllByText('PAPER').length).toBeGreaterThan(0)
    expect(screen.getAllByText('RESEARCH').length).toBeGreaterThan(0)
    expect(screen.getByText(/Không có lệnh thật/)).toBeInTheDocument()
    expect(screen.getByText(/PAPER ONLY/)).toBeInTheDocument()
  })

  it('contains no control for exchange order submission', () => {
    render(<App />)
    const buttons = screen.getAllByRole('button').map((b) => b.textContent.toLowerCase())
    // Must not have real exchange actions
    expect(buttons.join(' ')).not.toMatch(/connect exchange|wallet|submit order|testnet/)
    // Must have paper bot controls
    const hasStart = buttons.some((b) => b.includes('khởi động bot') || b.includes('đang chạy'))
    expect(hasStart).toBe(true)
    const hasStop  = buttons.some((b) => b.includes('dừng'))
    expect(hasStop).toBe(true)
  })

  it('charts the committed synthetic broker snapshots without invented deltas', () => {
    render(<App />)
    const artifactRows = brokerEquityCsv.trim().split(/\r?\n/).slice(1).map((line) => {
      const [timestamp, equity] = line.split(',')
      return { timestamp, equity: Number(equity) }
    })
    const replay = buildOfflineReplay()
    expect(previewEquityCsv.replaceAll('\r\n', '\n')).toBe(brokerEquityCsv.replaceAll('\r\n', '\n'))
    expect(replay).toEqual(artifactRows)
    expect(replay.at(-1)).toEqual({ timestamp: '2024-01-01T02:05:00+00:00', equity: 10449.2125 })
    expect(buildOfflineReplay(42)).toEqual(artifactRows)
    expect(() => parseEquityArtifact('timestamp,equity\n2024-01-01T00:00:00+00:00,NaN')).toThrow('Invalid broker equity artifact schema')
    const missingBalance = brokerEquityCsv.replace(',10000.0,10000.0,0.0,', ',10000.0,,0.0,')
    expect(() => parseEquityArtifact(missingBalance)).toThrow('Invalid broker equity artifact row')
  })

  it('derives public fold and audit figures from byte-matching committed evidence', () => {
    for (const [name, copy] of [
      ['walk_forward.report.json', foldReport],
      ['public_dataset_manifest.json', publicManifest],
      ['artifact_audit.json', artifactAudit],
    ]) {
      const original = JSON.parse(readFileSync(resolve(process.cwd(), `../docs/reviews/evidence/stage-06-11-repair/${name}`), 'utf8'))
      expect(copy).toEqual(original)
    }
    expect(evidence.historicalWindow.datasetHash).toBe(publicManifest.datasets['1m'].sha256)
    expect(evidence.strategies.map((row) => row.result)).toEqual(
      foldReport.report.aggregate.map((row) => `${row.total_net_pnl.toFixed(4)} USDT`),
    )
    expect(evidence.artifactAudit.absolutePathsFound).toBe(artifactAudit.absolute_paths_found)
  })

  it('renders coin switcher with BTC, ETH, SOL buttons', () => {
    render(<App />)
    // All 3 coins must be present as pressable nav buttons
    expect(screen.getByRole('button', { name: /BTCUSDT/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /ETHUSDT/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /SOLUSDT/i })).toBeInTheDocument()
    // Switching coin changes the active coin
    fireEvent.click(screen.getByRole('button', { name: /ETHUSDT/i }))
    const ethBtn = screen.getByRole('button', { name: /ETHUSDT/i })
    expect(ethBtn.getAttribute('aria-pressed')).toBe('true')
  })

  it('starts and stops the paper bot without submitting real orders', () => {
    render(<App />)
    // Find start button by text content (has leading symbol)
    const allButtons = screen.getAllByRole('button')
    const startBtn = allButtons.find((b) => /khởi động bot/i.test(b.textContent))
    expect(startBtn).toBeTruthy()
    expect(startBtn).not.toBeDisabled()
    // Start bot
    fireEvent.click(startBtn)
    // Button text becomes "Đang chạy..." and is disabled
    const runningBtn = allButtons.find((b) => /đang chạy/i.test(b.textContent))
    expect(runningBtn).toBeTruthy()
    expect(runningBtn).toBeDisabled()
    // Stop button becomes active
    const stopBtn = allButtons.find((b) => /dừng/i.test(b.textContent))
    expect(stopBtn).not.toBeDisabled()
    fireEvent.click(stopBtn)
    // Back to start state — re-query since re-render
    const allBtnsAfter = screen.getAllByRole('button')
    const startAgain = allBtnsAfter.find((b) => /khởi động bot/i.test(b.textContent))
    expect(startAgain).not.toBeDisabled()
  })

  it('shows paper account panel with initial equity and broker safety note', () => {
    render(<App />)
    // Account panel shows starting equity
    expect(screen.getAllByText(/10,000/).length).toBeGreaterThan(0)
    // Broker note (appears in multiple elements — use getAllByText)
    expect(screen.getByText(/PaperBroker mô phỏng/)).toBeInTheDocument()
    // Circuit breaker
    expect(screen.getByText(/Circuit breaker/i)).toBeInTheDocument()
    // No real exchange note (multiple occurrences on page)
    expect(screen.getAllByText(/không có lệnh sàn thật/i).length).toBeGreaterThan(0)
  })
})
