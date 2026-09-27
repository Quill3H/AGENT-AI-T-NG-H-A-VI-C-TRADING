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

describe('paper research console', () => {
  it('renders the safety and evidence boundary', () => {
    render(<App />)
    expect(screen.getByText('PAPER / RESEARCH — NO LIVE ORDERS')).toBeInTheDocument()
    expect(screen.getAllByText('AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED').length).toBeGreaterThan(0)
    expect(screen.getByText(/21 expected boundaries/)).toBeInTheDocument()
    expect(screen.getByText(/11 exact-ready/)).toBeInTheDocument()
    expect(screen.getByText(/10 delayed/)).toBeInTheDocument()
  })

  it('contains no control for exchange order submission', () => {
    render(<App />)
    const buttons = screen.getAllByRole('button').map((button) => button.textContent.toLowerCase())
    expect(buttons).toEqual(['inspect archived replay'])
    expect(buttons.join(' ')).not.toMatch(/buy|sell|submit order|connect exchange|wallet/)
  })

  it('runs the deterministic offline demo exactly once', () => {
    render(<App />)
    const button = screen.getByRole('button', { name: 'Inspect archived replay' })
    fireEvent.click(button)
    expect(screen.getByRole('button', { name: 'Replay inspected' })).toBeDisabled()
    expect(screen.getByText('65 / 65 artifact snapshots displayed')).toBeInTheDocument()
    expect(screen.getByText('No economic claim · no orders sent')).toBeInTheDocument()
    expect(buildOfflineReplay()).toEqual(buildOfflineReplay())
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
    expect(screen.getByRole('link', { name: 'Equity CSV' })).toHaveAttribute('href', expect.stringContaining('/equity_curve.csv'))
    const duplicate = `${brokerEquityCsv.trim()}\n${brokerEquityCsv.trim().split(/\r?\n/).at(-1)}`
    expect(() => parseEquityArtifact(duplicate)).toThrow('Invalid broker equity artifact row')
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

  it('clearly presents flat design category badges and non-coder explanations', () => {
    render(<App />)
    // Three explicit data tiers
    expect(screen.getAllByText('Số liệu minh họa').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Kết quả lịch sử đã lưu trữ').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Dữ liệu chẩn đoán mẫu').length).toBeGreaterThan(0)

    // Non-coder explanations
    expect(screen.getByText(/Dành cho người không biết code/)).toBeInTheDocument()
    expect(screen.getByText(/Vì sao không gọi là "Chạy bot"\?/)).toBeInTheDocument()
    expect(screen.getByText(/Nguyên tắc an toàn Fail-Closed/)).toBeInTheDocument()

    // Friendly strategy names
    expect(screen.getAllByText('Bám theo xu hướng').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Phá vỡ cản & Kiểm tra lại').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Quét thanh khoản dòng tiền lớn (SMC)').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Khai thác chênh lệch phí Funding').length).toBeGreaterThan(0)
  })

  it('renders KPI metric cards and snapshot table upon replay inspection', () => {
    render(<App />)
    expect(screen.getByText(/10,000.00/)).toBeInTheDocument()
    expect(screen.getByText(/10,449.21/)).toBeInTheDocument()
    expect(screen.getByText('KHÓA HOÀN TOÀN')).toBeInTheDocument()

    const button = screen.getByRole('button', { name: 'Inspect archived replay' })
    fireEvent.click(button)

    expect(screen.getByText('Mốc thời gian (UTC)')).toBeInTheDocument()
    expect(screen.getByText(/2024-01-01T01:01:00\+00:00 \(Bắt đầu\)/)).toBeInTheDocument()
    expect(screen.getByText(/2024-01-01T02:05:00\+00:00 \(Kết thúc\)/)).toBeInTheDocument()
  })
})
