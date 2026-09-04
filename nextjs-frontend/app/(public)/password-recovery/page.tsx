"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { passwordReset } from "@/components/actions/password-reset-action";
import { useActionState } from "react";
import { SubmitButton } from "@/components/ui/submitButton";
import Link from "next/link";
import { FormError } from "@/components/ui/FormError";

export default function Page() {
  const [state, dispatch] = useActionState(passwordReset, undefined);

  return (
    <div className="flex h-screen w-full items-center justify-center bg-background px-4">
      <form action={dispatch} className="w-full max-w-sm">
        <Card className="w-full rounded-lg shadow-lg">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-semibold">
              Password Recovery
            </CardTitle>
            <CardDescription className="text-sm">
              Enter your email to receive instructions to reset your password.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6 p-6">
            <div className="grid gap-3">
              <Label htmlFor="email">
                Email<span className="relative -top-1 text-sm text-destructive">*</span>
              </Label>
              <Input
                id="email"
                name="email"
                type="email"
                placeholder="m@example.com"
                required
              />
            </div>
            <SubmitButton text="Send" />
            <FormError state={state} />
            <div className="mt-2 text-sm text-center text-primary">
              {state?.message && <p>{state.message}</p>}
            </div>
            <div className="mt-4 text-center text-sm text-muted-foreground">
              <Link
                href="/login"
                className="text-primary hover:text-primary/80"
              >
                Back to login
              </Link>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
