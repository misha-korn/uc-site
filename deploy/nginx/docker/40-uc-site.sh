#!/bin/sh
# Выбор конфига nginx по наличию сертификата Let's Encrypt + автоматическое применение
# нового/продлённого сертификата без перезапуска контейнера.
#   нет сертификата → http.conf.template (сайт по http, проходит проверка certbot)
#   есть сертификат → https.conf.template (http → https, TLS)
# Раз в минуту проверяется, не появился ли/не обновился ли сертификат; если да — nginx -s reload.
set -eu

: "${SITE_DOMAIN:?Задайте SITE_DOMAIN в .env (например, indiga.ru)}"
CERT="/etc/letsencrypt/live/${SITE_DOMAIN}/fullchain.pem"
KEY="/etc/letsencrypt/live/${SITE_DOMAIN}/privkey.pem"
OUT=/etc/nginx/conf.d/default.conf

state() {
    # «подпись» сертификата: путь файла в archive/ меняется при каждом продлении
    if [ -f "$CERT" ] && [ -f "$KEY" ]; then
        echo "https:$(readlink -f "$CERT"):$(stat -c %Y "$(readlink -f "$CERT")")"
    else
        echo "http"
    fi
}

render() {
    case "$1" in
        https:*) tpl=https ;;
        *)       tpl=http ;;
    esac
    envsubst '${SITE_DOMAIN}' < "/etc/nginx/uc-site/${tpl}.conf.template" > "$OUT"
    echo "[uc-site] режим nginx: ${tpl} (${SITE_DOMAIN})"
}

current="$(state)"
render "$current"

(
    while sleep 60; do
        new="$(state)"
        if [ "$new" != "$current" ]; then
            render "$new"
            if nginx -t -q; then
                nginx -s reload && echo "[uc-site] сертификат изменился — nginx перезагружен"
                current="$new"
            else
                echo "[uc-site] ошибка в конфиге, оставляю прежний" >&2
                render "$current"
            fi
        fi
    done
) &
