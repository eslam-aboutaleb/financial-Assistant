import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import AuthModal from '../src/components/AuthModal'

describe('AuthModal', () => {
  it('renders login mode by default', () => {
    render(<AuthModal onAuthenticated={() => {}} />)
    expect(screen.getByText('Sign In to OmniCare')).toBeInTheDocument()
    expect(screen.getByText("Don't have an account? Sign up")).toBeInTheDocument()
  })

  it('switches to sign up mode', () => {
    render(<AuthModal onAuthenticated={() => {}} />)
    const toggle = screen.getByText("Don't have an account? Sign up")
    fireEvent.click(toggle)
    expect(screen.getByText('Create an Account')).toBeInTheDocument()
    expect(screen.getByText('Already have an account? Sign in')).toBeInTheDocument()
  })
})
