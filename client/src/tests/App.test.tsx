import { render, screen } from "@testing-library/react";
import App from "../App";
import { AuthProvider } from "../auth/AuthContext";

test("renders the auth screen when logged out", () => {
  localStorage.clear();
  render(
    <AuthProvider>
      <App />
    </AuthProvider>
  );
  expect(screen.getByText(/triage agent/i)).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: /register profile/i })).toBeInTheDocument();
});
