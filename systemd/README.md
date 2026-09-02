# Services

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
