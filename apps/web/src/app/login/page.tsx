"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Input } from "@/components/ui/input";
import { StumplineIcon } from "@/components/brand/StumplineIcon";

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [organization, setOrganization] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { login, register } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (isRegister) {
        await register(email, password, name, organization || undefined);
      } else {
        await login(email, password);
      }
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex lg:w-1/2 flex-col items-center justify-center bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 p-12 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,_var(--tw-gradient-stops))] from-blue-900/30 via-transparent to-transparent pointer-events-none" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,_var(--tw-gradient-stops))] from-slate-800/40 via-transparent to-transparent pointer-events-none" />

        <div className="relative z-10 flex flex-col items-center text-center max-w-sm">
          <StumplineIcon className="h-16 w-16 text-primary mb-6" />
          <h1 className="text-4xl font-extrabold bg-gradient-to-r from-primary to-blue-300 bg-clip-text text-transparent mb-3">
            Stumpline
          </h1>
          <p className="text-lg text-slate-300 font-medium mb-10">
            Cricket intelligence. Match precision.
          </p>

          <ul className="space-y-4 text-left w-full">
            {[
              { title: "Live match analytics", desc: "real-time win probabilities and run rates" },
              { title: "Predictive modelling", desc: "ML-powered match outcome predictions" },
              { title: "Deep player & team stats", desc: "across every IPL season" },
            ].map((f) => (
              <li key={f.title} className="flex items-start gap-3">
                <span className="mt-1.5 h-2 w-2 rounded-full bg-primary shrink-0" />
                <span className="text-slate-300 text-sm">
                  <span className="font-semibold text-white">{f.title}</span> — {f.desc}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center bg-background px-6 py-12">
        <div className="w-full max-w-md">
          <div className="flex lg:hidden flex-col items-center mb-8">
            <StumplineIcon className="h-12 w-12 text-primary mb-3" />
            <span className="text-2xl font-bold bg-gradient-to-r from-primary to-blue-300 bg-clip-text text-transparent">
              Stumpline
            </span>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-bold text-foreground mb-1">
              {isRegister ? "Create your account" : "Welcome back"}
            </h2>
            <p className="text-muted-foreground text-sm">
              {isRegister ? "Start analysing cricket with Stumpline" : "Sign in to your Stumpline account"}
            </p>
          </div>

          <form
            onSubmit={handleSubmit}
            className="bg-card border border-border rounded-xl p-6 space-y-4"
          >
            {error && (
              <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-4 py-2">
                {error}
              </div>
            )}

            {isRegister && (
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-foreground mb-1">
                  Full Name
                </label>
                <Input id="name" type="text" required value={name} onChange={(e) => setName(e.target.value)} placeholder="John Doe" />
              </div>
            )}

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-foreground mb-1">
                Email
              </label>
              <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-foreground mb-1">
                Password
              </label>
              <Input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" />
            </div>

            {isRegister && (
              <div>
                <label htmlFor="org" className="block text-sm font-medium text-foreground mb-1">
                  Organization <span className="text-muted-foreground">(optional)</span>
                </label>
                <Input id="org" type="text" value={organization} onChange={(e) => setOrganization(e.target.value)} placeholder="Your team or company" />
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-primary hover:bg-primary/90 text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? "Please wait..." : isRegister ? "Create Account" : "Sign In"}
            </button>

            <div className="text-center text-sm text-muted-foreground">
              {isRegister ? "Already have an account?" : "Don't have an account?"}{" "}
              <button
                type="button"
                onClick={() => {
                  setIsRegister(!isRegister);
                  setError("");
                }}
                className="text-primary hover:underline font-medium"
              >
                {isRegister ? "Sign in" : "Create one"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
