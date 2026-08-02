# Base image: python:3.13-slim pinned by digest (SDLC card t_b94f2853).
# Upgrade rationale (verified 2026-08-01):
#   - python:3.12-slim latest digest (57cd7c3a...) is identical to the Jul 24
#     audit scan; the tag has not moved, so "latest" 3.12 buys no new patches.
#   - 3.13-slim ships pip 26.1.2 (fixes pip 25.0.1 CVEs flagged in audit);
#     3.12-slim still ships pip 25.0.1.
#   - Both images share the same Debian trixie (13.6) base; apt-get upgrade
#     reports 0 installable updates, so the remaining glibc/libacl/etc. CVEs
#     have no upstream Debian fix available yet (none in KEV, exploit prob <5%).
#   - Pinning the digest makes rebuilds reproducible (monitor flagged unpinned tag).
FROM python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY alembic.ini .
COPY alembic/ alembic/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
CMD ["./entrypoint.sh"]
