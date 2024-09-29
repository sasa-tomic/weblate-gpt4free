# Install deps

```
rye sync
```

# Configure

Copy `config/config.yml.example` to `config/config.yml` and edit configuration.

# Run

```
rye run python3 scripts/run_translation.py
```

# Update all deps

```
rye sync
rye lock --update-all
```
