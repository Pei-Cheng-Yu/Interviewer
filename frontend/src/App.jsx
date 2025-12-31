import React from "react";
import { Routes, Route, Navigate, Link, useLocation } from "react-router-dom";

import ProtectedRoute from "./ProtectedRoute.jsx";

import LoginPage from "./LoginPage.jsx";
import RegisterPage from "./RegisterPage.jsx";

import OnboardPage from "./pages/OnboardPage.jsx";
import InterviewPage from "./pages/InterviewPage.jsx";
import HistoryPage from "./pages/HistoryPage.jsx";
import ReviewPage from "./pages/ReviewPage.jsx";

function TopBar() {
  const location = useLocation();
  const path = location.pathname;

  const isInterview = path.startsWith("/interview/");
  const isAuthPage = path.startsWith("/login") || path.startsWith("/register");

  // Hide nav on interview + auth pages
  if (isInterview || isAuthPage) return null;

  return (
    <div className="topbar">
      <div className="brand">Interviewer</div>
      <div className="nav">
        <Link className="navLink" to="/onboard">
          Onboard
        </Link>
        <Link className="navLink" to="/history">
          History
        </Link>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <div className="appShell">
      <TopBar />
      <div className="page">
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Default entry: go login first */}
          <Route path="/" element={<Navigate to="/login" replace />} />

          {/* Protected */}
          <Route
            path="/onboard"
            element={
              <ProtectedRoute>
                <OnboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/interview/:sessionId"
            element={
              <ProtectedRoute>
                <InterviewPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/history"
            element={
              <ProtectedRoute>
                <HistoryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/review/:sessionId"
            element={
              <ProtectedRoute>
                <ReviewPage />
              </ProtectedRoute>
            }
          />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </div>
    </div>
  );
}
