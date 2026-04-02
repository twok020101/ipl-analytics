"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchVenues } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { MapPin, Trophy, TrendingUp } from "lucide-react";
import Link from "next/link";

export default function VenuesPage() {
  const { data: venues, isLoading, isError } = useQuery({
    queryKey: ["venues"],
    queryFn: fetchVenues,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <MapPin className="h-6 w-6 text-primary" />
          Venues
        </h1>
        <p className="text-muted-foreground mt-1">IPL cricket grounds and their statistics</p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(9)].map((_, i) => <Skeleton key={i} className="h-44" />)}
        </div>
      ) : isError ? (
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            Failed to load venues. Ensure the API is running.
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {(venues || []).map((venue) => (
            <Link key={venue.id} href={`/venues/${venue.id}`}>
              <Card className="h-full transition-all duration-300 hover:border-gray-700 hover:shadow-lg hover:-translate-y-0.5 cursor-pointer group">
                <CardContent className="p-6">
                  <div className="flex items-start justify-between mb-3">
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold group-hover:text-primary transition-colors truncate">
                        {venue.name}
                      </h3>
                      <p className="text-sm text-muted-foreground flex items-center gap-1 mt-0.5">
                        <MapPin className="h-3 w-3" />
                        {venue.city}
                      </p>
                    </div>
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 ml-3">
                      <MapPin className="h-5 w-5 text-primary" />
                    </div>
                  </div>
                  <div className="mt-4">
                    <div className="p-2.5 rounded-lg bg-gray-800/50 text-center">
                      <p className="text-xs text-muted-foreground">Matches Played</p>
                      <p className="text-lg font-bold text-primary">{venue.matches_played || 0}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
