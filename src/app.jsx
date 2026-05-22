import { Component } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext.jsx";
import { AppProvider, useApp } from "./context/AppContext.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import WorkspacePage from "./pages/WorkspacePage.jsx";
import Shell from "./shell.jsx";

class ErrorBoundary extends Component {
  state = { err: null };
  static getDerivedStateFromError(err) { return { err }; }
  render() {
    if (!this.state.err) return this.props.children;
    return (
      <div style={{ padding: 32, fontFamily: "monospace", fontSize: 13 }}>
        <div style={{ color: "#DC2626", fontWeight: 700, marginBottom: 8 }}>Error de renderizado</div>
        <pre style={{ background: "#FEF2F2", border: "1px solid #FECACA", padding: 12, borderRadius: 6, whiteSpace: "pre-wrap", wordBreak: "break-word", color: "#7F1D1D" }}>
          {this.state.err.message}
        </pre>
        <button onClick={() => { this.setState({ err: null }); window.location.reload(); }}
          style={{ marginTop: 12, padding: "6px 16px", background: "#2563EB", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}>
          Recargar
        </button>
      </div>
    );
  }
}

function AppRouter() {
  const { isLoggedIn } = useAuth();
  const { workspaceReady } = useApp();

  if (!isLoggedIn)      return <LoginPage />;
  if (!workspaceReady)  return <WorkspacePage />;
  return <Shell />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <AppProvider>
          <AppRouter />
        </AppProvider>
      </AuthProvider>
    </ErrorBoundary>
  );
}
