import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { App } from './App'
import { buildOfflineReplay } from './lib/replay'

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
    expect(buttons).toEqual(['run offline demo replay'])
    expect(buttons.join(' ')).not.toMatch(/buy|sell|submit order|connect exchange|wallet/)
  })

  it('runs the deterministic offline demo exactly once', () => {
    render(<App />)
    const button = screen.getByRole('button', { name: 'Run offline demo replay' })
    fireEvent.click(button)
    expect(screen.getByRole('button', { name: 'Replay complete' })).toBeDisabled()
    expect(screen.getByText('12 / 12 steps processed')).toBeInTheDocument()
    expect(screen.getByText('No economic claim · no orders sent')).toBeInTheDocument()
    expect(buildOfflineReplay()).toEqual(buildOfflineReplay())
  })
})
