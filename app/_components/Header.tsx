"use client";
import Image from "next/image";
import Link from "next/link";
import { SignInButton, UserButton, useUser } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";

export default function Header() {
  const { user } = useUser();

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-50">
      <Link href="/" className="flex items-center gap-2">
        <Image src="/logo.png" alt="Logo" width={36} height={36} />
        <span className="text-base font-semibold">
          AI Video <span className="text-primary">Course</span>
        </span>
      </Link>

      <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-muted-foreground">
        <Link href="/" className="hover:text-foreground transition-colors">Home</Link>
        <Link href="/pricing" className="hover:text-foreground transition-colors">Pricing</Link>
      </nav>

      {user ? (
        <UserButton afterSignOutUrl="/" />
      ) : (
        <SignInButton mode="modal">
          <Button size="sm">Get Started</Button>
        </SignInButton>
      )}
    </header>
  );
}