# Cidade Alerta
### Automatização Inteligente da Gestão de Ocorrências Urbanas

## Desenvolvimento com Docker

Executa os comandos na pasta `app/`.

### Primeira utilização
Constrói a imagem e inicia a aplicação:

```bash
docker compose up -d --build
```

### Utilização habitual
Inicia a aplicação:

```bash
docker compose up -d
```

Abre [localhost:8080](http://localhost:8080) no browser.

### Após alterações ao código
Reinicia o serviço e atualiza o browser quando a compilação terminar:

```bash
docker compose restart app
```

### Parar a aplicação

```bash
docker compose down
```
