"use client";
import { useEffect } from "react";

export function Login({ res, theme }: { res: { accessToken: string; refresh_token: string }; theme: string }) {
  useEffect(() => {
    // ruleid: eos-web-storage-token
    localStorage.setItem("accessToken", res.accessToken);
    // ruleid: eos-web-storage-token
    window.sessionStorage.setItem("refresh_token", res.refresh_token);
    // ruleid: eos-web-storage-token
    localStorage["auth"] = res.accessToken;
    // ruleid: eos-web-storage-token
    localStorage.jwt = res.accessToken;
    // ok: eos-web-storage-token
    localStorage.setItem("theme", theme);
    // ok: eos-web-storage-token
    sessionStorage.setItem("lastTab", "orders");
  }, [res, theme]);
  // ruleid: eos-client-private-env
  const key = process.env.STRIPE_SECRET_KEY;
  // ok: eos-client-private-env
  const site = process.env.NEXT_PUBLIC_SITE_URL;
  // ok: eos-client-private-env
  const dev = process.env.NODE_ENV === "development";
  // ruleid: eos-js-eval-sink
  eval(theme);
  // ruleid: eos-js-eval-sink
  const f = new Function("a", theme);
  // ruleid: eos-js-eval-sink
  setTimeout("alert(1)", 10);
  // ok: eos-js-eval-sink
  setTimeout(() => console.log(site), 10);
  return <p>{String(key)}{String(dev)}{String(f)}</p>;
}
