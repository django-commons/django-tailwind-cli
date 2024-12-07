---
hide:
  - navigation
---

# Usage

!!! question "Do I have to install the Tailwind CLI?"

    **No.** The management commands of this library handle the download and installation of the Tailwind CLI. You don't have to deal with this. But you can configure the installation location and the version of the CLI you want to use. Take a look at the [settings](settings.md) section.

!!! question "Do I have to create my own `tailwind.config.js`?"

    **No.** The management commands also take care of this step. If no `tailwind.config.js` is present in your project, a new one with sane defaults will be created. Afterwards this file will be used and be customized by you. The default location for the file is the `BASE_DIR` of your project, but you can change this. Take a look at the [settings](settings.md) section.

## Management commands

### build

Run `python manage.py tailwind build` to create an optimized production built of the stylesheet. Afterwards you are ready to deploy. Take care the this command is run before `python manage.py collectstatic` in your build process.

### download_cli

Run `python manage.py tailwind download_cli` to just download the CLI. This commands downloads the correct version of the CLI for your platform and stores it in the path configured by the `TAILWIND_CLI_PATH` setting.

### list_templates

Run `python manage.py tailwind list_templates` to find all templates in your django project. This is handy for a setup where you dynamically build the list of files being analyzed by tailwindcss.

### remove_cli

Run `python manage.py tailwind remove_cli` to remove the installed cli.

### runserver

Run `python manage.py tailwind runserver` to start the classic Django debug server in parallel to a tailwind watcher process.

```shell
Usage: ./manage.py tailwind runserver [OPTIONS] [ADDRPORT]

  Start the Django development server and the Tailwind CLI in watch mode.

Arguments:
  [ADDRPORT]  Optional port number, or ipaddr:port

Options:
  -6, --ipv6     Tells Django to use an IPv6 address.
  --nothreading  Tells Django to NOT use threading.
  --nostatic     Tells Django to NOT automatically serve static files at
                STATIC_URL.
  --noreload     Tells Django to NOT use the auto-reloader.
  --skip-checks  Skip system checks.
  --help         Show this message and exit.
```

### runserver_plus

Run `python manage.py tailwind runserver` to start the extended debug server from the [django-extensions](https://django-extensions.readthedocs.io/en/latest/runserver_plus.html) package in parallel to a tailwind watcher process. It offers some nice additions an interactive debug console, SSL support and so on.

```shell
Usage: ./manage.py tailwind runserver_plus [OPTIONS] [ADDRPORT]

  Start the django-extensions runserver_plus development server and the
  Tailwind CLI in watch mode.

Arguments:
  [ADDRPORT]  Optional port number, or ipaddr:port

Options:
  -6, --ipv6            Tells Django to use an IPv6 address.
  --nothreading         Tells Django to NOT use threading.
  --nostatic            Tells Django to NOT automatically serve static files
                        at STATIC_URL.
  --noreload            Tells Django to NOT use the auto-reloader.
  --skip-checks         Skip system checks.
  --pdb                 Drop into pdb shell at the start of any view.
  --ipdb                Drop into ipdb shell at the start of any view.
  --pm                  Drop into (i)pdb shell if an exception is raised in a
                        view.
  --print-sql           Print SQL queries as they're executed.
  --print-sql-location  Show location in code where SQL query generated from.
  --cert-file TEXT      SSL .crt file path. If not provided path from --key-
                        file will be selected. Either --cert-file or --key-
                        file must be provided to use SSL.
  --key-file TEXT       SSL .key file path. If not provided path from --cert-
                        file will be selected. Either --cert-file or --key-
                        file must be provided to use SSL.
  --help                Show this message and exit.
```

### watch

Run `python manage.py tailwind watch` to just start a tailwind watcher process if you prefer to start your debug server in a seperate shell or prefer a different solution than runserver or runserver_plus.

## Use with PyCharm

[PyCharm](https://www.jetbrains.com/pycharm/) is a great IDE, but its Tailwind CSS plugin doesn't work well with the standalone CLI this package uses. Luckily, there is a [workaround](https://youtrack.jetbrains.com/issue/WEB-55647/Support-Tailwind-css-autocompletion-using-standalone-tailwind-CLI#focus=Comments-27-10957961.0-0) for this.

### install_pycharm_workaround

Run `python manage.py tailwind install_pycharm_workaround` to install the workaround in your project.

!!! info "Update .gitignore file"


    Update your `.gitignore` manually so that it exludes the created `package.json` file and the `node_modules` directory, that is created by this management command.

    ```gitignore
    package.json
    node_modules/
    ```

### remove_pycharm_workaround

Run `python manage.py tailwind install_pycharm_workaround` to remove the workaround from your project.

## Use with Docker Compose

When used in the `watch` mode, the Tailwind CLI requires a TTY-enabled environment to function correctly. In a Docker Compose setup, ensure that the container executing the Tailwind style rebuild command (either `python manage.py tailwind runserver` or `python manage.py tailwind watch`, as noted above) is configured with the `tty: true` setting in your `docker-compose.yml`.

```yaml
web:
  command: python manage.py tailwind runserver
  tty: true

# or

tailwind-sidecar:
  command: python manage.py tailwind watch
  tty: true
```
