"use client";

import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { login } from "@/components/actions/login-action";
import { useActionState } from "react";
import { SubmitButton } from "@/components/ui/submitButton";
import { FieldError, FormError } from "@/components/ui/FormError";

export default function Page() {
  const [state, dispatch] = useActionState(login, undefined);
  return (
    <div className="flex h-screen w-full items-center justify-center bg-background px-4">
      <form action={dispatch} className="w-full max-w-sm">
        <Card className="w-full rounded-lg shadow-lg">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-semibold">
              Login
            </CardTitle>
            <CardDescription className="text-sm">
              로그인 아이디(4~32자)와 비밀번호를 입력하세요.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6 p-6">
            <div className="grid gap-3">
              <Label htmlFor="username">
                로그인 아이디<span className="relative -top-1 text-sm text-destructive">*</span>
              </Label>
              <Input
                id="username"
                name="username"
                type="text"
                minLength={4}
                maxLength={32}
                placeholder="4~32자"
                required
              />
              <FieldError state={state} field="username" />
            </div>
            <div className="grid gap-3">
              <Label htmlFor="password">
                Password<span className="relative -top-1 text-sm text-destructive">*</span>
              </Label>
              <Input
                id="password"
                name="password"
                type="password"
                required
              />
              <FieldError state={state} field="password" />
              <Link
                href="/password-recovery"
                className="ml-auto inline-block text-sm text-primary hover:text-primary/80"
              >
                Forgot your password?
              </Link>
            </div>
            <SubmitButton text="Sign In" />
            <FormError state={state} />
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
