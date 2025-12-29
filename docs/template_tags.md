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
