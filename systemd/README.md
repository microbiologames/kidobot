# Services

Trois services, sur deux machines différentes.

## Sur le PC de la maison

`llama-server` (le modèle) et `kidobot-serveur` (transcription + voix).

```bash
echo "KIDOBOT_JETON=$(openssl rand -hex 16)" | sudo tee /etc/kidobot-serveur.env
sudo chmod 600 /etc/kidobot-serveur.env
sudo cp systemd/kidobot-serveur.service /etc/systemd/system/
sudo systemctl enable --now kidobot-serveur
```

Reportez le même jeton dans `config/kidobot.toml` de la boîte (`stt.jeton` et
`tts.jeton`), et pensez à ouvrir les ports 8080 et 8100 sur le réseau local
uniquement — jamais vers l'extérieur.

Vérification depuis la boîte :

```bash
curl http://192.168.1.20:8100/sante      # {"etat":"ok"}
curl http://192.168.1.20:8080/health     # llama.cpp
```

## Sur la boîte

```bash
sudo useradd -m -G audio,gpio,spi,i2c kidobot     # si l'utilisateur n'existe pas
sudo -u kidobot git clone https://github.com/microbiologames/kidobot /home/kidobot/kidobot

echo 'ANTHROPIC_API_KEY=sk-ant-...' | sudo tee /etc/kidobot.env
sudo chmod 600 /etc/kidobot.env
sudo chown kidobot /etc/kidobot.env

sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now llama-server kidobot
```

Adaptez `--model` dans `llama-server.service` au fichier réellement téléchargé
par `scripts/fetch_models.sh`.

Diagnostic :

```bash
journalctl -u kidobot -f          # ce que fait la boîte, en direct
journalctl -u llama-server -n 50  # chargement du modèle, vitesse d'inférence
curl localhost:8080/health        # le cerveau local répond-il ?
```

En mode `llm.backend = "claude"` uniquement, `llama-server` est inutile :
`sudo systemctl disable --now llama-server`.
