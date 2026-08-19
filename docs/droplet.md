sudo systemctl restart salle-automate
cd frontend && npm run build


nano /var/www/salle_automate/.env

sudo systemctl status salle-automate --no-pager