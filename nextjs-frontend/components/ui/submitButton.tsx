import { useFormStatus } from "react-dom";
import { Button } from "@/components/ui/button";

export function SubmitButton({
  text,
  disabled,
  className,
}: {
  text: string;
  disabled?: boolean;
  className?: string;
}) {
  const { pending } = useFormStatus();

  return (
    <Button
      className={className ?? "w-full disabled:opacity-50 disabled:cursor-not-allowed"}
      type="submit"
      disabled={pending || disabled}
    >
      {pending ? "Loading..." : text}
    </Button>
  );
}
