#!/bin/sh
# Separate dev container for the AI Dashboard work. Does not touch odoo-dev,
# odoo-dev-2 or any of their databases.
#   web:  http://localhost:8075   (database: aidash, login admin / admin)
#   code: AI_Dashboard/addons is mounted at /mnt/extra-addons (no rsync needed)
export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

docker rm -f levelix-aidash >/dev/null 2>&1
docker run -d \
  --name levelix-aidash \
  --restart unless-stopped \
  --shm-size=1g \
  --network odoo-community-dev_odoo-net \
  -p 8075:8069 \
  -e HOST=db -e USER=odoo -e PASSWORD=admin123 -e ODOO_RC=/etc/odoo/odoo.conf \
  -v "$HERE/addons":/mnt/extra-addons \
  -v "$HERE/scripts":/mnt/scripts:ro \
  -v aidash-data:/var/lib/odoo \
  -v "$HERE/scripts/odoo.conf":/etc/odoo/odoo.conf:ro \
  odoo-custom:19.0 \
  odoo
