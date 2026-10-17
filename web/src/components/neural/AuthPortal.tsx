"use client";

import React, { useState } from "react";
import { User } from "@/lib/types";
import { loginUser, signupUser, getGoogleAuthUrl } from "@/lib/api";
import {
  Mail,
  Lock,
  User as UserIcon,
  AlertCircle,
  Loader2,
  Sparkles,
  X,
  ShieldCheck,
  ArrowRight,
} from "lucide-react";

interface AuthPortalProps {
  isOpen: boolean;
  onClose?: () => void;
  onSuccess: (user: User) => void;
  initialMode?: "login" | "signup";
}

export function AuthPortal({
  isOpen,
  onClose,
  onSuccess,
  initialMode = "login",
}: AuthPortalProps) {
  const [mode, setMode] = useState<"login" | "signup">(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedEmail = email.trim().toLowerCase();
    if (!trimmedEmail || !trimmedEmail.includes("@")) {
      setError("Please enter a valid email address.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }

    if (mode === "signup" && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      if (mode === "login") {
        const user = await loginUser(trimmedEmail, password);
        onSuccess(user);
      } else {
        const user = await signupUser(trimmedEmail, password, name.trim() || undefined);
        onSuccess(user);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleAuth = async () => {
    setGoogleLoading(true);
    try {
      const url = await getGoogleAuthUrl();
      window.location.href = url;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not initiate Google OAuth flow.");
      setGoogleLoading(false);
    }
  };


  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 select-none">
      {/* Dimmed Atmospheric Backdrop */}
      <div
        className="fixed inset-0 bg-black/80 backdrop-blur-xl animate-fade-in"
        onClick={onClose}
      />

      {/* Cybernetic Glass Card */}
      <div className="relative w-full max-w-md rounded-3xl bg-[#0c0f18]/95 border border-white/[0.08] shadow-[0_20px_60px_rgba(0,0,0,0.8)] p-6 sm:p-8 z-10 overflow-hidden">
        {/* Subtle Top Gradient Line */}
        <div className="absolute top-0 left-0 right-0 h-[1.5px] bg-gradient-to-r from-transparent via-cyan-400/60 to-transparent" />

        {/* Close Button */}
        {onClose && (
          <button
            onClick={onClose}
            className="absolute top-5 right-5 p-1.5 rounded-lg text-zinc-500 hover:text-white hover:bg-white/[0.05] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}

        {/* Header Monolith */}
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-500/20 to-cyan-500/20 border border-cyan-500/30 flex items-center justify-center mb-3 shadow-[0_0_20px_rgba(6,182,212,0.2)]">
            <Sparkles className="w-6 h-6 text-cyan-300" />
          </div>
          <h2 className="text-xl font-bold tracking-tight text-white font-sans">
            {mode === "login" ? "Access Lamit Neural" : "Initialize Identity"}
          </h2>
          <p className="text-xs text-zinc-400 mt-1 max-w-xs font-sans">
            PostgreSQL session-authenticated environment with zero-leak multi-tenant isolation.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="grid grid-cols-2 p-1 rounded-xl bg-white/[0.03] border border-white/[0.05] mb-5 text-xs font-medium">
          <button
            type="button"
            onClick={() => {
              setMode("login");
              setError(null);
            }}
            className={`py-2 rounded-lg transition-all ${
              mode === "login"
                ? "bg-indigo-600/30 text-white border border-indigo-500/40 shadow-sm"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("signup");
              setError(null);
            }}
            className={`py-2 rounded-lg transition-all ${
              mode === "signup"
                ? "bg-indigo-600/30 text-white border border-indigo-500/40 shadow-sm"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            Create Account
          </button>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-950/30 border border-rose-500/30 flex items-start gap-2.5 text-xs text-rose-300">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <span className="flex-1">{error}</span>
          </div>
        )}

        {/* Google OAuth Fast Path */}
        <button
          type="button"
          onClick={handleGoogleAuth}
          disabled={googleLoading || loading}
          className="w-full flex items-center justify-center gap-3 py-2.5 px-4 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-medium text-white transition-all mb-4 disabled:opacity-50"
        >
          {googleLoading ? (
            <Loader2 className="w-4 h-4 animate-spin text-zinc-400" />
          ) : (
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
          )}
          <span>Continue with Google</span>
        </button>

        {/* Divider */}
        <div className="flex items-center gap-3 my-4">
          <div className="h-px bg-white/[0.06] flex-1" />
          <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">
            or credentials
          </span>
          <div className="h-px bg-white/[0.06] flex-1" />
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-3.5">
          {mode === "signup" && (
            <div>
              <label className="block text-[11px] font-mono text-zinc-400 mb-1">
                Name / Handle
              </label>
              <div className="relative flex items-center">
                <UserIcon className="w-4 h-4 text-zinc-500 absolute left-3 pointer-events-none" />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ada Lovelace"
                  className="w-full bg-black/40 border border-white/[0.08] focus:border-indigo-500/50 rounded-xl pl-9 pr-3.5 py-2 text-xs text-white placeholder:text-zinc-600 outline-none transition-colors"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-[11px] font-mono text-zinc-400 mb-1">
              Email Address
            </label>
            <div className="relative flex items-center">
              <Mail className="w-4 h-4 text-zinc-500 absolute left-3 pointer-events-none" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="architect@domain.com"
                className="w-full bg-black/40 border border-white/[0.08] focus:border-indigo-500/50 rounded-xl pl-9 pr-3.5 py-2 text-xs text-white placeholder:text-zinc-600 outline-none transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-mono text-zinc-400 mb-1">
              Password
            </label>
            <div className="relative flex items-center">
              <Lock className="w-4 h-4 text-zinc-500 absolute left-3 pointer-events-none" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full bg-black/40 border border-white/[0.08] focus:border-indigo-500/50 rounded-xl pl-9 pr-3.5 py-2 text-xs text-white placeholder:text-zinc-600 outline-none transition-colors"
              />
            </div>
          </div>

          {mode === "signup" && (
            <div>
              <label className="block text-[11px] font-mono text-zinc-400 mb-1">
                Confirm Password
              </label>
              <div className="relative flex items-center">
                <Lock className="w-4 h-4 text-zinc-500 absolute left-3 pointer-events-none" />
                <input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full bg-black/40 border border-white/[0.08] focus:border-indigo-500/50 rounded-xl pl-9 pr-3.5 py-2 text-xs text-white placeholder:text-zinc-600 outline-none transition-colors"
                />
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || googleLoading}
            className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white text-xs font-semibold shadow-lg shadow-indigo-500/25 transition-all flex items-center justify-center gap-2 mt-4 disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin text-white" />
            ) : (
              <>
                <span>{mode === "login" ? "Authenticate" : "Create Identity"}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </form>

        {/* Security Assurance Badge */}
        <div className="mt-5 pt-4 border-t border-white/[0.04] flex items-center justify-center gap-2 text-[10px] font-mono text-zinc-500">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Argon2id Hashes • HTTP-Only Cookies • PostgreSQL Isolation</span>
        </div>
      </div>
    </div>
  );
}
