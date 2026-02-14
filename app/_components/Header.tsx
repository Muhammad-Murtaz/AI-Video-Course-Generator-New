"use client";
import Image from "next/image";
import Link from "next/link";
import { SignInButton, UserButton, useUser } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";

export default function Header() {
  const { user } = useUser();

  return (
    <div className="flex items-center justify-between p-4">
      <div className="flex items-center gap-2">
        <Image src="/logo.png" alt="Logo" width={40} height={40} />
        <h2 className="text-lg font-medium">
          AI Video <span className="text-primary">Course</span>
        </h2>
      </div>

      <ul className="flex gap-8 items-center text-lg font-medium">
        <Link href="/">
          <li className="hover:text-primary cursor-pointer">Home</li>
        </Link>
        <Link href="/pricing">
          <li className="hover:text-primary cursor-pointer">Pricing</li>
        </Link>
      </ul>

      {user ? (
        <UserButton />
      ) : (
        <SignInButton mode="modal">
          <Button>Get Started</Button>
        </SignInButton>
      )}
    </div>
  );
}