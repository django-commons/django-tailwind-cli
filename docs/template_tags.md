# Template Tags

## `{% tailwind_css %}`

Put this template tag in the head of your base template. It includes the `link`-tags to load the CSS stylesheets.

```htmldjango
{% load tailwind_cli %}
...
<head>
    ...
    {% tailwind_css %}
    ...
</head>
```

Depending on the value of the variable `settings.DEBUG` it also activates preloading.

- `DEBUG = False` creates the following output:

  ```html
  <link rel="preload" href="/static/css/styles.css" as="style" />
  <link rel="stylesheet" href="/static/css/styles.css" />
  ```

- `DEBUG = True` creates this output:

  ```html
  <link rel="stylesheet" href="/static/css/styles.css" />
  ```

### Optional `name` Parameter

When using `TAILWIND_CLI_CSS_MAP` for multiple CSS entry points, you can optionally filter
which CSS files to include by passing a name:

```htmldjango
{# Include all CSS files defined in CSS_MAP #}
{% tailwind_css %}

{# Include only the "admin" entry #}
{% tailwind_css "admin" %}

{# Include only the "web" entry #}
{% tailwind_css "web" %}
```

The name corresponds to the source filename (without extension and path) defined in your
`TAILWIND_CLI_CSS_MAP` setting. For example, with this configuration:

```python
TAILWIND_CLI_CSS_MAP = [
    ("styles/admin.css", "css/admin.output.css"),
    ("styles/web.css", "css/web.output.css"),
]
```

- `{% tailwind_css "admin" %}` includes only `css/admin.output.css`
- `{% tailwind_css "web" %}` includes only `css/web.output.css`
- `{% tailwind_css %}` includes both files

If the specified name doesn't match any entry, no output is generated.
