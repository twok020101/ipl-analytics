import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse-slow rounded-lg bg-gray-800", className)}
      {...props}
    />
  );
}

export { Skeleton };
