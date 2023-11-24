# mobo

MOckBOt: A Discord/ChatGPT bot that can take on whatever personality you write.

Running:

```shell
source .env
docker run \
  -d \
  -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
  -e DISCORD_API_KEY="${DISCORD_API_KEY}" \
  -e PERSONALITY_URL=https://gist.githubusercontent.com/cjonesy/3876ce2b74d70762a84cf651acce615a/raw/7d5cf0d1d1e68f2291a3a1468ff210771842ebed/clyde \
  ghcr.io/cjonesy/mobo:main
```
