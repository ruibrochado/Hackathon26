# Desenvolvimento web com Docker

Requisitos: Docker Engine/Docker Desktop e Docker Compose. Executar na pasta `app/`.
O Docker usa Flutter 3.41.4 (Dart 3.11.1); nao e necessario instalar Flutter na maquina.
O Supabase continua remoto. O ficheiro `.env` existente e lido pela app como asset;
cada colega deve obter a configuracao publica de desenvolvimento pelo canal da equipa.
Nunca colocar chaves secretas/service_role no frontend. O `.env` nao entra na imagem.

## Arrancar

```sh
docker compose up -d --build
docker compose logs -f app
```

Quando o servidor estiver pronto, abrir http://localhost:8080 manualmente.
A primeira compilacao descarrega o SDK e as dependencias e pode demorar.
O modo web-server tem debugging limitado relativamente ao modo Chrome.

## Alteracoes ao codigo

O codigo local esta montado no contentor. Para recompilar de forma previsivel:

```sh
docker compose restart app
```

Aguardar a compilacao nos logs e atualizar o browser. Nao se promete hot reload automatico.
Para parar: `docker compose down`. As caches persistem nos volumes Docker.

## Dependencias

Guardar `pubspec.yaml` e `pubspec.lock` no Git. O arranque usa
`flutter pub get --enforce-lockfile` para rejeitar um lockfile desatualizado.
Apos alterar intencionalmente o pubspec, atualizar o lockfile dentro do Docker:

```sh
docker compose stop app
docker compose run --rm app flutter pub get
docker compose up -d
```

Rever e guardar o novo lockfile no Git. Evitar `pub upgrade` sem necessidade.
Para outros comandos: `docker compose exec app flutter analyze`.

## Utilizadores Linux

O utilizador do contentor tem UID/GID 1000 por omissao. Se os teus forem diferentes,
usa `DEV_UID=$(id -u) DEV_GID=$(id -g) docker compose build` na primeira construcao.
Os volumes existentes conservam o seu proprietario; nao partilhar caches entre UIDs diferentes.

## Configuracao e limites

O `.env` e preservado: nao precisa de uma variavel FLUTTER_VERSION.
A versao do SDK esta fixada em Dockerfile.dev. Alteracoes a esse ficheiro requerem --build.
As dependencias Ubuntu podem receber atualizacoes; isto nao e uma imagem bit a bit reproduzivel.
Docker uniformiza o ambiente web, mas nao acrescenta suporte web a plugins apenas mobile.
Se OAuth redirecionar para um endereco errado, verificar os URLs autorizados no Supabase
para http://localhost:8080 e a rota de callback usada pela app.
