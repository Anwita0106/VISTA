import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Badge, Input, Modal } from "../components/ui";
import { AuthProvider } from "../context/AuthContext";
import Login from "../pages/Login";

describe("UI components", () => {
  it("renders a status badge with a readable label", () => {
    render(<Badge value="IN_PROGRESS" />);
    expect(screen.getByText("In Progress")).toHaveAttribute("data-status", "IN_PROGRESS");
  });
  it("links a field error to its input for screen readers", () => {
    render(<Input label="Email" id="email" error="Email is required" />);
    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", "email-error");
  });
  it("closes a modal with the Escape key", async () => {
    const onClose = vi.fn();
    render(<Modal open title="Test" onClose={onClose}><input aria-label="x" /></Modal>);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});

describe("Login page", () => {
  it("shows validation errors without calling the API", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<MemoryRouter><AuthProvider><Login /></AuthProvider></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByText("Email is required")).toBeInTheDocument();
    expect(screen.getByText("Password is required")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
  it("shows the server error for invalid credentials", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Invalid email or password" }), { status: 401 }));
    render(<MemoryRouter><AuthProvider><Login /></AuthProvider></MemoryRouter>);
    await userEvent.type(screen.getByLabelText("Email"), "x@y.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Invalid email or password")).toBeInTheDocument();
  });
});
