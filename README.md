![Main test status](https://img.shields.io/github/actions/workflow/status/marckrenn/places-env/test.yaml?branch=main&label=Test%20(main))
![Develop test status](https://img.shields.io/github/actions/workflow/status/marckrenn/places-env/test.yaml?branch=develop&label=Test%20(develop))
[![PyPI - Version](https://img.shields.io/pypi/v/places-env)](https://pypi.org/project/places-env/)
![GitHub License](https://img.shields.io/github/license/marckrenn/places-env)
# places-env: secure version control of environment files
> **Note:**  
> _places-env_ is currently a proof of concept (PoC) and is **not ready for use in public projects or production environments**. Use it cautiously and only with private repositories.  
> If you appreciate the ideas behind _places-env_, consider contributing by submitting pull requests!

## Motivation / The heck is _places-env_?

![Schematic overview of places](https://raw.githubusercontent.com/marckrenn/places-env/5a99cc9245ca6c8ea9d3cb4adb67d2f2cee56c09/images/places-dark.svg?sanitize=true#gh-dark-mode-only)
![Schematic overview of places](https://raw.githubusercontent.com/marckrenn/places-env/5a99cc9245ca6c8ea9d3cb4adb67d2f2cee56c09/images/places-light.svg?sanitize=true#gh-light-mode-only)

- _places-env_ is a self-contained, completely free open-source (FOSS) alternative to [HashiCorp Vault](https://www.hashicorp.com/products/vault), [Infisical](https://infisical.com/), [dotenv-vault](https://github.com/dotenv-org/dotenv-vault) and [sops](https://github.com/getsops/sops).  
- Leverages a single source of truth (SSOT) [`places.yaml`](#placesyaml) for deriving multiple environment files.
- Similar to [sops](https://github.com/getsops/sops), _places-env_ encrypts only the values in [`places.yaml`](#placesyaml), resulting in [`places.enc.yaml`](#placesencyaml), which can be securely checked into git:  
  - Congrats, your SSOT is now version-controlled 🎉
  - Always synchronized with collaborators
  - Fully in-sync with the rest of your code, branches and tags (try doing that with [Infisical](https://infisical.com/) & co. 😉) 
  - Changes remain 'human-trackable' — even when values are encrypted
  - Contrary to [sops](https://github.com/getsops/sops), encryption keys can be assigned either per environment or on a per-value basis
- Provides a [straightforward setup](#getting-started) with no dependency on external services or libraries.  
- [`places watch start`](#watch-start) (persistently) tracks changes in [`places.yaml`](#placesyaml)/[`places.enc.yaml`](#placesencyaml) and automatically handles [encryption](#encrypt), [decryption](#decrypt), [keeps `.gitignore` up-to-date](#sync-gitignore), and [auto-updates](#generate-environment) environment files. So it's essentially _set and forget_.

<details>

<summary>Fallback Image (for Github Mobile users)</summary>

![Schematic overview of places](https://github.com/marckrenn/places-env/blob/develop/images/places-dark.png?raw=True)

</details>

## Getting started

1. **Install _places-env_:**

- via [pypi](https://pypi.org/project/places-env/):

    `pip install places-env`

2. **Init project:** In terminal
  - `cd` into your project  
  - Run one of the following commands:  
    - [`places init`](#init): Creates an empty [`places.yaml`](#placesyaml), generates a default crypto key at `.places/keys/default`
    - [`places init --template min`](#init): Initializes with a minimal template ([view content](src/places/templates/min.yaml)).  
    - [`places init --tutorial`](#init): Initializes with a tutorial template ([view content](src/places/templates/tutorial.yaml)).

3. **Modify [`places.yaml`](#placesyaml)**:
  - Use your preferred text editor  
  - Or modify it using the [_places-env_ CLI](#places-cli-documentation)

4. **Track changes:**
  - Use [`places watch start (optionally: --daemon, --service)`](#watch-start) (recommended)  
  - Alternatively, use [`places encrypt`](#encrypt) and [`places sync gitignore`](#sync-gitignore). This will automatically add all necessary entries to `.gitignore`.

5. **Generate environment files:**
  - If [`places watch start`](#watch-start) is already running, environments with property `watch: true` will be (re)generated whenever [`places.yaml`](#placesyaml) is updated.  
  - Or use [`places generate environment --all`](#generate-environment) to manually regenerate all environment files.

6. **Commit [`places.enc.yaml`](#placesencyaml)**

7. **Decrypt after switching to another branch**:
  - If [`places watch start`](#watch-start) is already running, [`places.enc.yaml`](#placesencyaml) will automatically be decrypted into [`places.yaml`](#placesyaml) after switching branches.  
  - Otherwise, run [`places decrypt`](#decrypt) to manually derive [`places.yaml`](#placesyaml) from [`places.enc.yaml`](#placesencyaml).

8. **Key exchange:**
  - If you're working with collaborators, **securely** share your crypto keys located in `.places/keys` with them.
  - Recommended methods include shared password managers like [Bitwarden](https://bitwarden.com/), secure one-time sharing services, or dedicated tools such as [Amazon KMS](https://aws.amazon.com/kms/).
  - Collaborators without the necessary decryption keys can still add and edit new secrets but are restricted from reading existing ones.

## Example / Demo

A "live" example / demo project can be found [here](https://github.com/marckrenn/places-env-example).

## CI/CD

_places-env_ has a companion GitHub Action you can find on the GitHub Marketplace [here](https://github.com/marketplace/actions/places-env). It installs _places-env_, injects crypto keys and generates environment files so that they can be used downstream in your CI/CD workflow.

## Documentation

### `places.yaml`

#### Examples

1. [Minimal example](src/places/templates/min.yaml):
```yaml
key: .places/keys/default

environments:
  local:
    filepath: .env
    watch: true

variables:
  PROJECT_NAME: your-project-name
```

[`places generate environment local`](#generate-environment) or [`places watch start`](#watch-start) will generate this `.env` for environment `local`:

```
PROJECT_NAME=your-project-name
```


2. Closer-to-live example based on the [tutorial template](src/places/templates/tutorial.yaml):
```yaml

keys:
  default: .places/keys/default
  prod: .places/keys/prod
  dev: .places/keys/dev
  test: .places/keys/test

environments:

  local:
    filepath: .env
    watch: true
    key: default

  development:
    filepath: .env.dev
    alias: [dev]
    key: dev

  production:
    filepath: .env.prod
    alias: [prod]
    key: prod

variables:

  PROJECT_NAME: your-project-name

  HOST: localhost

  PORT:
    local: 8000
    dev: 8001
    prod:
      value: 8002
      unencrypted: true
  
  ADDRESS: ${HOST}:${PORT}

  DOMAIN:
    dev: ${PROJECT_NAME}.foo.dev
    prod: ${PROJECT_NAME}.foo.com
  
  JSON_MULTILINE: |
    {
      "key1": "value1",
      "key2": "value2"
    }

```

[`places generate environment --all`](#generate-environment) or [`places watch start`](#watch-start) will generate

* this `.env` for environment `local`:
```
PROJECT_NAME=your-project-name
HOST=localhost
PORT=8000
ADDRESS=localhost:8000
JSON_MULTILINE='{
  "key1": "value1",
  "key2": "value2"
}'
```

* this `.env.dev` for environment `development`:
```
PROJECT_NAME=your-project-name
HOST=localhost
PORT=8001
ADDRESS=localhost:8001
DOMAIN=your-project-name.foo.dev
JSON_MULTILINE='{
  "key1": "value1",
  "key2": "value2"
}'
```

* and this `.env.prod` for environment `production`:
```
PROJECT_NAME=your-project-name
HOST=localhost
PORT=8002
ADDRESS=localhost:8002
DOMAIN=your-project-name.foo.com
JSON_MULTILINE='{
  "key1": "value1",
  "key2": "value2"
}'
```
<details>
<summary>CLI commands:</summary>

- Encrypt the values in [`places.yaml`](#placesyaml) and saves the encrypted data to [`.places/places.enc.yaml`](#placesencyaml):
    
    [`places encrypt`](#encrypt)

</details>

#### Sections

All sections are case-sensitive!

**Required sections:**
- [`key` / `keys`](#key--keys)
- [`environments`](#environments)
- [`variables`](#variables)

**Optional section:**
- [`settings`](#settings)

##### `key` / `keys`

Encryption/decryption key or keys that can be referenced in [`environments`](#environments).  

The `default` key is required as it serves as a fallback when no other key is specified.

**Examples:**

```yaml
key: .places/keys/default # shorthand for keys: default: .places/keys/default
```

```yaml
keys:
  default: .places/keys/default
  dev: .places/keys/dev
  prod: .places/keys/prod
  topsecret: .places/keys/topsecret
```

<details>
<summary>CLI commands:</summary>

- Generate key, add it to `.places/keys/` and optionally add key to [`places.yaml`](#placesyaml):
    
    [`places generate key`](#generate-key)

- Add a key from string to `.places/keys/` and optionally add the key to [`places.yaml`](#placesyaml):

    [`places add key_from_string`](#add-key_from_string)

- Add existing key to [`places.yaml`](#placesyaml):

    [`places add key`](#add-key)

</details>

##### `environments`

`environments` define what environment file(s) should be generated.

**Example:**
```yaml
environments:
  local:
    filepath: .env
    watch: true
  development:
    filepath: .env.dev
    watch: true
    alias: [dev, stage]
    key: dev
  production:
    filepath: .env.prod
    watch: true
    alias: [prod]
    key: prod
```

**Options**:

| Option | Type | Default | Required | Description |
|--------|------|---------|:--------:|-------------|
| `filepath` | `String` | `None` | ✅ | filepath of environment file to generate relative to root |
| `key` | `Bool` | `default` | ❌ | Key to encrypt / decrypt variables of this environment. Refers to keys defined in [keys](#key--keys) |
| `alias` | `[String]` | `None` | ❌ |Alias(es) that can be used for this environment|
| `watch` | `Bool` | `false` | ❌ | If `true` and [`places watch start`](#watch-start) is running, this environment will be auto-(re)generated on filechange of [`places.yaml`](#placesyaml) |

<details>
<summary>CLI commands:</summary>
- Add or modify environment in [`places.yaml`](#placesyaml):

    [`places add environment`](#add-environment)
</details>

##### `variables`

Key-value pairs to save to environment file(s). Keys should contain only uppercase alphanumerics and underscores; otherwise, a warning is printed.

**Example:**

```yaml
variables:

  PROJECT_NAME: your-project-name

  HOST: localhost

  PORT:
    local: 8000
    dev: 8001
    prod:
      value: 8002
      unencrypted: true
  
  ADDRESS: ${HOST}:${PORT}

  DOMAIN:
    dev: ${PROJECT_NAME}.foo.dev
    prod: ${PROJECT_NAME}.foo.com
  
  JSON: |
    {
      'key1': 'value1',
      'key2': 'value2'
    }
```

**Syntax**:

- Shorthand: Set a key-value for all [environments](#environments). **Note: This will encrypt the value separately with the keys of all environments. Any of these keys will be able to decrypt it!**

    ```yaml
    VARIABLE_NAME: value
    ```

- Set specific value per [environment](#environments)

    ```yaml
    PORT:
        local: 8000
        dev: 8001
        prod: 8002
    ```

- Set specific encryption key per value [environment](#environments)

    ```yaml
    SECRET:
        local:
            value: This won't be encrypted # in places.enc.yaml
            unencrypted: true
        prod:
            value: Dirty secret # will be encrypted with 'topsecret' key
            key: topsecret # must be defined in keys section
    ```

- Multiline strings (must start with `|`):
    ```yaml
    JSON: |
        {
        'key1': 'value1',
        'key2': 'value2'
        }
    ```
- Single-line dicts must be explicitly wrapped into quotes:
    ```yaml
    JSON: "{'key1': 'value1', 'key2': 'value2'}"
    ```

- Value interpolation:

    ```yaml
    HOST: localhost

    PORT:
        local: 8000
        dev: 8001
        prod: 8002
    
    ADDRESS: ${HOST}:${PORT} # .env = localhost:8000, .env.dev = localhost:8001, etc.
    ```

- Lists/arrays with square brackets (**Note:** yaml-multiline arrays are currently NOT supported, see [Known Issues](#known-issues--limitations)!)

    ```yaml
    ARRAY: [1,2,3,4]
    ```

- Combination of all syntaxes above.

**Options**:

| Option | Type | Default | Required | Description |
|--------|------|---------|:--------:|-------------|
| `value` | `Any` | `None` | ✅ | value of Key |
| `key` | `String` | `key set in` [environments](#environments) `> default key` | ❌ | encryption / decryption key used for this particular value |
| `unencrypted` | `Bool` | `False` | ❌ | If `true` explicitly not encrypt value |

<details>
<summary>CLI commands:</summary>

- Add variable to [`places.yaml`](#placesyaml):
    
    [`places add variable`](#add-variable)

</details>

##### `settings`

Allows for configuration of project parameters, primarily related to cryptography.

**Examples:**
```yaml
settings:
    sync-gitingore: false
    cryptography:
        hash-function: sha265
        iterations: 120000
        dklen: 32
        salt:
            mode: from-file
            filepath: version.txt
```

**Options:**

| Option | Type | Default | Required | Description |
|--------|------|---------|:--------:|-------------|
| `sync-gitignore` | `Bool` | `True` | ❌ | If `true` makes sure that all `.envs`, [`places.yaml`](#placesyaml) and `.places` are in `.gitignore` |
| `cryptography`:`hash-function` | `String` | `sha512` | ❌ | Hash function to encrypt / decrypt (`sha256` or `sha512`) |
| `cryptography`:`iterations` | `Int` | `600000` (`sha265`), `210000` (`sha512`) | ❌ | Hash function to encrypt / decrypt (`sha256` or `sha512`) |
| `cryptography`:`dklen` | `Int` | `32` | ❌ | Derived key length |
| `cryptography`:`salt`:`mode` | `String` | `deterministic` | ❌ | Available modes: `deterministic`[^1], `custom`[^2], `from-file`[^3], `git-project`[^4], `git-branch`[^5], `git-project-branch`[^6] |

[^1]: By default, _places-env_ intentionally uses a deterministic salt. While this allows for some statistical attacks, it enables tracking of value changes.
[^2]: Set a custom salt using `cryptography`:`salt`:`value`.  
[^3]: Use the content of `cryptography`:`salt`:`filepath` as the salt (e.g., salting with `version.txt`).
[^4]: Use the Git project name as the salt.  
[^5]: Use the Git branch as the salt (encrypted values will differ for each branch).  
[^6]: Combine the Git project name and branch as the salt.


<details>
<summary>CLI commands:</summary>

- Add settings to [`places.yaml`](#placesyaml):
    
    [`places add setting`](#add-setting)

</details>

### `places.enc.yaml`

The encrypted version of [`places.yaml`](#placesyaml), which is safe to check into Git.

**Example:**
```yaml
keys:
  default: .places/keys/default
  prod: .places/keys/prod
  dev: .places/keys/dev
  test: .places/keys/test

environments:

  local:
    filepath: .env
    watch: true
    key: default

  development:
    filepath: .env.dev
    alias: [dev]
    key: dev

  production:
    filepath: .env.prod
    alias: [prod]
    key: prod

variables:

  PROJECT_NAME: encrypted(default|dev|prod):kvvmBtvz6I8QadAG5hoDyEZ8kzbfJ2IrGwpNlqD70CWIpWfSlzR6TA==|ddts1k4JhTNmP9f9zrfCyfM6dcth5eP86y9UoCQwGvqmrCW02Y4jwg==|1037LUJgxus4CsF35VtwZ/FjFuioG/PGwzaMuJwGI4GRdKA+eiH0gQ==

  HOST: encrypted(default|dev|prod):levmXeHNoZcRN6dHdvE5GZTG8TpBCqD8IxpjtA==|cstsjXQ3zCtnYaC8IPmbMqGVIeONE5EA4QIVyw==|0F37dnhej/M5VLY2xqHJWGrwGUBGg9KWVYPSXA==

  PORT:
    local: encrypted(default):uOieQPXb5MVQjSDnUF7EXkVfEKHRC2aJ
    dev: encrypted(dev):X8gUkGAxiXkySxxyJeDZiABVBFr7JbGD
    prod:
      value: 8002
      unencrypted: true
  
  ADDRESS: encrypted(default|dev|prod):kp+sUOvf4KwlR6tO2hk9z29S5A/pQX1DgBN1LLeFNKwB2DNSnVulEsGPSuE=|db8mgH4ljRBTEay18rT8ztoUAvJXg/yU2hEhXMxD1DlIKFauN2tO6uCKsNU=|1ymxe3JMzsgNJLo/2VhOYNhNYdGefeyuzEl4GkNBfe4rss/5PfZpdaUCf9Y=

  DOMAIN:
    dev: encrypted(dev):db8mgHgm/hRWObjIwqa1tu44ceVK+of43zRKE0pthsnU3U7da7gqjvX5ZbqKjOdHZHPAfA==
    prod: encrypted(prod):1ymxe3RPvcwIDK5C6UoHGOxhEsaDBJfCyWwTVUA1GneBv+DzLbWmIphZPaAPZOd8xM6yYg==
  
  JSON_MULTILINE: encrypted(default|dev|prod):ktuwUPHZk4opXIIP9Scin0NF/DbfOGF6hAgNZjOVzfH5hckrOvVBaL80vB6mdBXPrfFFDYAbk7NXLdeQzHBuv9+lqoi4qetM|dfs6gGQj/jZfCoX03YrjnvYDGsth+uCt3gpZFmt98sXH6GOMmolif4Wj2Zz3KyUGhEiioMYmbHKq2o77duYEKxY+woyWEKFA|122te2hKve4BP5N+9mZRMPRaeeioBPCXyFIAUGElbnqq4KSiQIxsoqc6ZQpj1FexDm9Ya7iPKKkjOcl8JqtuUEtYmQWfu9uX

```
<details>
<summary>CLI commands:</summary>

- Decrypts and derives [`places.yaml`](#placesyaml) from [`places.enc.yaml`](#placesencyaml):
    
    [`places decrypt`](#decrypt)

</details>

## FAQ

- **The hell is this? Do you have _any_ idea what you're doing?**  
    > No. Consider this a toy, a conversation starter. If this gains traction, those who truly know how things should be done will need to take over.  
    > This is my first public Python project/package, and it's full of firsts for me, so please keep that in mind. Also, I don't consider myself a professional programmer and have no formal education in this domain.

- **Why?**  
    > This started as a Hackathon project, and I felt the urge to complete and release something for once. Additionally, I'm preparing a tech stack I’d like to work with, and I wasn’t satisfied with the existing workflows for managing and syncing secrets (see below).

- **Is this for me/my project?**  
    > Again, consider this a toy. For now, use it only for private repositories and only with people you trust.

- **What happens if a collaborator doesn't have all the crypto keys defined in [`places.yaml`](#placesyaml)?**

  > - **For per-environment values (e.g., `PORT: local: 8000`)**:  
    If a collaborator lacks the required keys, [`places decrypt`](#decrypt) will fail to decrypt the encrypted value. In this case, the unencrypted value will remain in [`places.yaml`](#placesyaml) as-is. When re-encrypting with [`places encrypt`](#encrypt), the existing encrypted value will be written to [`places.enc.yaml`](#placesencyaml) unchanged.

  > - **For shorthand/compound values (e.g., `PROJECT_NAME: your-project-name`) that use multi/compound keys**:  
    If the user possesses any of the required keys (e.g. `default` and `dev` out of `encrypted(default|dev|prod):kvvmBt…`), [`places decrypt`](#decrypt) will successfully decrypt the value. When encrypting with [`places encrypt`](#encrypt), all keys (e.g. `default` and `dev`) available to the user will be used to encrypt the value.

  > - **Important Consideration**:  
    Compound values should only be used for non-sensitive information. For sensitive values, define them explicitly per environment.

- **Is _places-env_ secure?**  
    > Arguably, yes—especially when used in private repositories and among trusted collaborators. In general, _places-env_ exposes encrypted data to others (collaborators or the public), meaning that with enough time, effort and ressources, encrypted values could eventually be cracked. However, _places-env_ was designed to make this unlikely within reasonable boundaries. For instance:  
    > - [`places sync gitignore`](#sync-gitignore) is executed automatically by default, which should help prevent unencrypted data from being committed.  
    > - [`places generate key`](#generate-key) generates cryptographic keys with appropriate length and entropy.
    > - Per default `AES-512-GCM` with 210,000 iterations (per [OWASP recommendations](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)) is used for cryptographic opersions (see [settings options](#settings) for more details).  
    >  
    > That said, some design decisions have been made that may weaken security:
    > - By default, a deterministic salt is used to allow for deterministic tracking of changes, which introduces some potential attack vectors. If security is critical, you can choose alternative salting strategies in [settings options](#settings).  
    > - The cryptographic key exchange between collaborators is manual, so it’s your responsibility to ensure it happens securely.  
    > - When using the shorthand to define a variable for multiple environment files, any encryption key can decrypt the encrypted value.  
    > - **If you identify any inherent security flaws in _places-env_, please let me know ASAP. Thank you!**

- **Instead of _places-env_ why not just use …**
    - … [sops](https://github.com/getsops/sops)?
        > To be honest, I was overwhelmed at first glance and didn’t even try it. It’s almost certainly better and more secure in every regard than _places-env_, but at the same time, it looks cumbersome to set up.  
        > Additionally, I didn’t like how it seems to require (or strongly encourage) the use of another (potentially overkill) service for key management. Also, it appears to focus on file-based encryption rather than allowing for easy value-based encryption.
    - … [dotenv-vault](https://github.com/dotenv-org/dotenv-vault)?
        > Similar to [sops](https://github.com/getsops/sops), it looks great and might be a better solution for your use case. It’s also the closest alternative to _places-env_, so you may want to check it out.
        > What I prefer about _places-env_ is that it doesn't lock you into the [dotenv.org](https://www.dotenv.org/)-ecosystem and that multiple environment files are derived from a single source of truth ([`places.yaml`](#placesyaml)). Additionally, [`places watch start`](#watch-start) persistently tracks changes in [`places.yaml`](#placesyaml) and automatically manages [encryption](#encrypt), [decryption](#decrypt), and [`auto-updates`](#generate-environment) for your environment files.
    - … [Infisical](https://infisical.com/)?
      > I genuinely wanted to like it, but their documentation is currently a mess. It took me over half an hour to locate their current Python library, which wasn’t even referenced in the documentation. I ultimately gave up, frustrated, when attempting to align secrets with my version tags.
    - … [HashiCorp Vault](https://www.hashicorp.com/products/vault)?
        > Yeah, [no](https://www.hashicorp.com/products/vault/pricing).
    - … git hooks?
        > Glad you asked! This project actually started as Git hooks, and you can find a very basic MVP in [places-mini](places-mini). It uses a single key to encrypt local environment files but lacks many of the convenient features of _places-env_. For example, you’ll need to manually ensure that all the appropriate entries are added to `.gitignore`, among other things. Also, it uses a naughty hack to track changes and force encryption. Don't use it.

- **Why is the code so bad?**
    > As I mentioned above, I’m neither a professional coder nor experienced with the Python ecosystem. Additionally, I’ve made some questionable decisions along the way.

- **Why can’t the generated environment files be styled, structured, or annotated?**
  > It's on the [roadmap](#roadmap) below.

## Roadmap (unordered)

* **Hombrew:** Distribute _places-env_ also via [Homebrew](https://brew.sh/)
* **Comments in environment files**: Add `comment`property to variables
* **Layouting in environment files**: Add "meta-variables" (eg. `places.section`) that add sections and linebreaks at gen-time.

## Known issues / Limitations
* _places-env_ does not adhere to the [YAML specifications](https://yaml.org/).
* Only arrays/lists in square brackets are supported, block style arrays aren't (yet).
* Single-line KV/JSON needs to be wrapped in quotes.

***
***

# places CLI Documentation

## add environment

Add a new environment configuration.

```shell
places add environment NAME [OPTIONS]
```

<details>

***

<summary>Options & Arguments</summary>


**Options**

| Short | Long Option | Description |
|-------|-------------|-------------|
| `-f` | `--filepath <String>` | Path to environment file. |
| `-w` | `--watch <Bool>` | Enable file watching. |
| `-a` | `--alias <String>` | Environment aliases. |
| `-k` | `--key <String>` | Key to use for encryption. |


**Arguments**

| Argument | Required |
|----------|----------|
| `NAME` | ❌ |

***

</details>

## add key

Add an existing key file reference to places.yaml

```shell
places add key NAME [OPTIONS]
```

<details>

***

<summary>Options & Arguments</summary>


**Options**

| Short | Long Option | Description |
|-------|-------------|-------------|
| `-a` | `--add` | Add key reference to places.yaml |


**Arguments**

| Argument | Required |
|----------|----------|
| `NAME` | ❌ |

***

</details>

## add key_from_string

Add a key from a provided string with the specified name.

```shell
places add key_from_string NAME KEY_STRING [OPTIONS]
```

<details>

***

<summary>Options & Arguments</summary>


**Options**

| Short | Long Option | Description |
|-------|-------------|-------------|
| `-a` | `--add` | Add key to places.yaml |
| `-f` | `--force-overwrite` | Force overwrite without safety checks. |


**Arguments**

| Argument | Required |
|----------|----------|
| `NAME` | ❌ |
| `KEY_STRING` | ❌ |

***

</details>

## add setting

Add or update settings configuration.

```shell
places add setting [OPTIONS]
```

<details>

***

<summary>Options</summary>


**Options**

| Short | Long Option | Description |
|-------|-------------|-------------|
| `-sg` | `--sync-gitignore <Bool>` | Enable/disable .gitignore sync. |
| `-i` | `--iterations <Int>` | Number of iterations for cryptography. |
| `-hf` | `--hash-function <String>` | Hash function for cryptography. |
| `-sm` | `--salt-mode <String>` | Salt mode for cryptography. |
| `-sf` | `--salt-filepath <String>` | Salt filepath for cryptography. |
| `-sv` | `--salt-value <String>` | Salt value for cryptography. |

***

</details>

## add variable

Add a new variable configuration.

```shell
places add variable NAME [OPTIONS]
```

<details>

***

<summary>Options & Arguments</summary>


**Options**

| Short | Long Option | Description |
|-------|-------------|-------------|
| `-v` | `--value <Any>` | Value of variable / secret. |
| `-k` | `--key <String>` | Key to use for encryption. |
| `-u` | `--unencrypt <Bool>` | Mark value as unencrypted. |
| `-e` | `--environment <String>` | Target environment(s). |


**Arguments**

| Argument | Required |
|----------|----------|
| `NAME` | ❌ |

***

</details>

## decrypt

Decrypts `.places/places.enc.yaml` into `places.yaml` file.

```shell
places decrypt [OPTIONS]
```

## encrypt

Encrypts `places.yaml` into `.places/places.enc.yaml` file.

```shell
places encrypt [OPTIONS]
```

## generate environment

Generate .env files for specified environments or all environments defined in `places.yaml`

This generally follows [https://dotenv-linter.github.io/](https://dotenv-linter.github.io/) rules, with the exception of alphabetical ordering.

```shell
places generate environment [ENVIRONMENT]... [OPTIONS]
```

<details>

***

<summary>Options & Arguments</summary>


**Options**

| Short | Long Option | Description |
|-------|-------------|-------------|
| `-a` | `--all` | Generate .env files for all environments. |


**Arguments**

| Argument | Required |
|----------|----------|
| `ENVIRONMENT` | ❌ |

***

</details>

## generate key

Generate a new encryption key with the specified name.

```shell
places generate key [NAME] [OPTIONS]
```

<details>

***

<summary>Options & Arguments</summary>


**Options**

| Short | Long Option | Description |
|-------|-------------|-------------|
| `-l` | `--length <Int>` | Custom length for generated key in bytes. |
| `-a` | `--add` | Add key to places.yaml |


**Arguments**

| Argument | Required |
|----------|----------|
| `NAME` | ❌ |

***

</details>

## init

Initialize a new places project.

Also generates a new default encryption key and adds it to `.places/keys/`.

```shell
places init [OPTIONS]
```

<details>

***

<summary>Options</summary>


**Options**

| Short | Long Option | Description |
|-------|-------------|-------------|
| `-t` | `--template <String>` | Template to use for initialization |
| `--list-templates` | `--list-templates` | List available templates |

***

</details>

## run test

Run tests.

Currently supported tests: e2e, cli.

Specify test names or use –all flag.

```shell
places run test [TESTS]... [OPTIONS]
```

<details>

***

<summary>Options & Arguments</summary>


**Options**

| Short | Long Option | Description |
|-------|-------------|-------------|
| `-a` | `--all` | Run all tests. |


**Arguments**

| Argument | Required |
|----------|----------|
| `TESTS` | ❌ |

***

</details>

## sync gitignore

Sync .gitignore with Places entries.

```shell
places sync gitignore [OPTIONS]
```

## watch start

Start watching for changes.

```shell
places watch start [OPTIONS]
```

<details>

***

<summary>Options</summary>


**Options**

| Short | Long Option | Description |
|-------|-------------|-------------|
| `-s` | `--service` | Run watcher as a persistent system service. |
| `-d` | `--daemon` | Run watcher as a background daemon. |

***

</details>

## watch stop

Stop watching for changes.

```shell
places watch stop [OPTIONS]
```

<details>

***

<summary>Options</summary>


**Options**

| Short | Long Option | Description |
|-------|-------------|-------------|
| `-s` | `--service` | Stop and remove persistent system service. |
| `-d` | `--daemon` | Stop daemon process. |

***

</details>
