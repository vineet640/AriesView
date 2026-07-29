// Local emulation of Azure AD token issuance + validation.
//
// In production, Azure AD issues tokens on login and the gateway validates
// each request's JWT against Azure AD public keys (RS256, JWKS). Locally we
// keep the same middleware shape but sign/verify with a dev secret. Claims
// mirror the production tokens: roles plus the portfolios the user may
// query — role-based access is enforced at the token level.

const jwt = require("jsonwebtoken");

const JWT_SECRET = process.env.JWT_SECRET || "ariesview-local-dev-secret";
const TOKEN_TTL = "8h";

// Demo directory standing in for the Azure AD tenant.
const USERS = {
  analyst: {
    password: "demo",
    name: "Acquisition Analyst",
    roles: ["acquisition"],
    portfolios: ["demo-portfolio"],
  },
  admin: {
    password: "demo",
    name: "Platform Admin",
    roles: ["admin"],
    portfolios: ["*"],
  },
};

function login(username, password) {
  const user = USERS[username];
  if (!user || user.password !== password) return null;
  const token = jwt.sign(
    { sub: username, name: user.name, roles: user.roles, portfolios: user.portfolios },
    JWT_SECRET,
    { expiresIn: TOKEN_TTL }
  );
  return { token, name: user.name, roles: user.roles, portfolios: user.portfolios };
}

function requireAuth(req, res, next) {
  const header = req.headers.authorization || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : null;
  if (!token) return res.status(401).json({ error: "Missing bearer token" });
  try {
    req.user = jwt.verify(token, JWT_SECRET);
    next();
  } catch {
    return res.status(401).json({ error: "Invalid or expired token" });
  }
}

module.exports = { login, requireAuth };
