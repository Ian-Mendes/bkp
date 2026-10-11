const isProd = process.env.NODE_ENV === "production";
const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// O Next injeta scripts inline; em dev também precisa de eval (hot reload).
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isProd ? "" : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  `connect-src 'self' ${api}${isProd ? "" : " ws:"}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const headers = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  // os links de e-mail levam o token na URL: não deixar vazar via Referer
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];
if (isProd) {
  headers.push({
    key: "Strict-Transport-Security",
    value: "max-age=31536000; includeSubDomains",
  });
}

/** @type {import('next').NextConfig} */
module.exports = {
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers }];
  },
};
