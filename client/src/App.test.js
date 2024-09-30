import { render, screen } from '@testing-library/react';
import App from './App';

test('renders planner and keyboard guidance', () => {
  render(<App />);
  expect(screen.getByText(/Shape a feasible term sequence/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /validate plan/i })).toBeInTheDocument();
  expect(screen.getByText(/Keyboard: select a course/i)).toBeInTheDocument();
});
