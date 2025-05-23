# mobo

MOckBOt: A Discord/ChatGPT bot that can take on whatever personality you write.

Running:

```shell
source .env
docker run \
  -d \
  -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
  -e DISCORD_API_KEY="${DISCORD_API_KEY}" \
  -e MOBO_PERSONALITY_URL=https://gist.githubusercontent.com/cjonesy/3876ce2b74d70762a84cf651acce615a/raw/7d5cf0d1d1e68f2291a3a1468ff210771842ebed/clyde \
  ghcr.io/cjonesy/mobo:main
```

## Configuration

Mobo can be configured using the following environment variables:

| Environment Variable           | Description                                            | Default   |
| ------------------------------ | ------------------------------------------------------ | --------- |
| `OPENAI_API_KEY`               | Your OpenAI API key                                    | Required  |
| `DISCORD_API_KEY`              | Your Discord API key                                   | Required  |
| `MOBO_PERSONALITY_URL`         | URL to load personality from                           | Optional  |
| `MOBO_MODEL`                   | OpenAI model to use                                    | gpt-4     |
| `MOBO_TEMPERATURE`             | Temperature for model responses                        | 0.5       |
| `MOBO_TOP_P`                   | Top_p for model responses (alternative to temperature) | None      |
| `MOBO_MAX_HISTORY_LENGTH`      | Maximum message history length                         | 300       |
| `MOBO_MAX_BOT_RESPONSES`       | Maximum bot responses in a row                         | 5         |
| `MOBO_LOG_LEVEL`               | Logging level                                          | INFO      |
| `MOBO_ENABLE_IMAGE_GENERATION` | Enable image generation                                | False     |
| `MOBO_MAX_DAILY_IMAGES`        | Maximum images per day                                 | 10        |
| `MOBO_IMAGE_MODEL`             | OpenAI image model to use                              | dall-e-3  |
| `MOBO_IMAGE_SIZE`              | Size of generated images                               | 1024x1024 |

> Note: Only one of `MOBO_TEMPERATURE` or `MOBO_TOP_P` should be set. If both
> are provided, `MOBO_TOP_P` takes precedence.

## Admin Commands

Administrators can configure the bot with the following commands:

| Command                            | Description                                      |
| ---------------------------------- | ------------------------------------------------ |
| `!admin help`                      | Shows available commands                         |
| `!admin get-personality`           | Shows current personality                        |
| `!admin set-personality <text>`    | Sets bot personality                             |
| `!admin set-personality-url <url>` | Sets personality from URL                        |
| `!admin reset-config`              | Resets bot configuration                         |
| `!admin get-model`                 | Shows current model                              |
| `!admin set-model <model>`         | Sets OpenAI model                                |
| `!admin get-randomness`            | Shows whether temperature or top_p is being used |
| `!admin get-temperature`           | Shows current temperature setting (if active)    |
| `!admin set-temperature <value>`   | Sets temperature (0.0-2.0) and disables top_p    |
| `!admin get-top-p`                 | Shows current top_p setting (if active)          |
| `!admin set-top-p <value>`         | Sets top_p (0.0-1.0) and disables temperature    |
| `!admin enable-images`             | Enables image generation                         |
| `!admin disable-images`            | Disables image generation                        |
| `!admin set-image-model <model>`   | Sets image model (dall-e-2 or dall-e-3)          |
| `!admin set-image-limit <number>`  | Sets daily image generation limit                |
| `!admin get-image-quota`           | Shows remaining daily image quota                |

## Image Generation

When image generation is enabled, the bot can generate images based on its
conversation. The bot will decide when an image is appropriate based on the
context. Images are limited to a configurable daily quota (default: 10 per day).

This feature requires OpenAI API access with image generation capabilities.

## Controlling Randomness

You can control the randomness of the bot's responses using either temperature
or top_p:

- **Temperature**: Controls randomness directly. Lower values (like 0.2) make
  responses more deterministic and focused, while higher values (like 1.5) make
  responses more creative and varied. Range: 0.0-2.0.

- **Top_p**: Controls randomness through nucleus sampling. The model considers
  the results of the tokens with top_p probability mass. Lower values (like 0.1)
  make responses more focused, while higher values (like 0.9) allow more
  variety. Range: 0.0-1.0.

Only one parameter (temperature or top_p) should be used at a time. Setting one
will automatically disable the other.
