# Base Template

The package also includes a minimal base template, which you can use as a starting point for your own project. It is a very simple template, which only includes the CSS stylesheets and the `tailwind_css` template tag. You can use by putting `{% extends "tailwind_cli/base.html" %}` into your template files.

```htmldjango title="tailwind_cli/base.html"
{% load tailwind_cli %}
<!DOCTYPE html>
<html lang="{{ LANGUAGE_CODE }}">
  <head>
    <meta charset="UTF-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Home{% endblock title %}</title>
    {% tailwind_css %}
    {% block extra_head %}{% endblock extra_head %}
  </head>
  <body>
    {% block content %}
    {% endblock content %}
    {% block extra_body %}{% endblock extra_body %}
  </body>
</html>
```
