"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, User, LogOut, Loader2 } from "lucide-react";

interface HeaderProps {
  title?: string;
}

export default function Header({ title = "CUA | Automation Dashboard" }: HeaderProps) {
  const router = useRouter();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
      });
      router.push("/login");
      router.refresh();
    } catch (error) {
      console.error("Logout failed:", error);
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <header className="bg-background/80 backdrop-blur-md border-b border-border py-4 px-6 flex items-center justify-between sticky top-0 z-10">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 border border-white/10 rounded-full flex items-center justify-center bg-white/5">
          <div className="w-4 h-4 rounded-full border-2 border-white/80"></div>
        </div>
        <h1 className="font-medium text-lg text-foreground tracking-tight">{title}</h1>
        <div className="ml-4 px-2.5 py-1 bg-white/5 border border-white/10 rounded-full text-[10px] font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.6)]" />
          System Online
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button className="text-muted-foreground hover:text-foreground transition-colors relative group">
          <Bell className="w-5 h-5 group-hover:scale-110 transition-transform" />
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-blue-500 rounded-full border-2 border-background" />
        </button>
        <div className="h-6 w-px bg-border mx-1" />
        <div className="flex items-center gap-3">
          <div className="text-right hidden sm:block">
            <p className="text-sm font-medium text-foreground">Admin User</p>
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Engineering</p>
          </div>
          <div className="w-8 h-8 bg-gradient-to-br from-white/20 to-white/5 rounded-full flex items-center justify-center border border-white/10 text-foreground">
            <User className="w-4 h-4" />
          </div>
        </div>
        <button
          onClick={handleLogout}
          disabled={isLoggingOut}
          className="ml-2 p-2 text-muted-foreground hover:text-foreground hover:bg-white/5 rounded-md transition-all disabled:opacity-50"
          title="Sign out"
        >
          {isLoggingOut ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <LogOut className="w-4 h-4" />
          )}
        </button>
      </div>
    </header>
  );
}
