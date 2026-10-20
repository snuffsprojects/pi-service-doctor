# Security

Pi Service Doctor is designed for a trusted LAN or an authenticated reverse proxy. Its report may reveal hostnames, service names, local ports, filesystem paths and software health. The dashboard has no authentication of its own.

The checker is read-only and exposes no browser control endpoint. Its systemd service runs as the selected unprivileged user with filesystem, privilege, kernel and control-group restrictions. Do not put secrets in labels, URLs or paths in `config.json`.

Please report security issues privately to the repository owner rather than opening a public issue. Never include credentials or an unredacted private health report.
