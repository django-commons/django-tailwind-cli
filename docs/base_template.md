# Base Template

The package also includes a minimal base template, which you can use as a starting point for your own project. It is a very simple template, which only includes the CSS stylesheets and the `tailwind_css` template tag. You can use by putting `{% extends "tailwind_cli/base.html" %}` into your template files.

```{literalinclude} ../src/django_tailwind_cli/templates/tailwind_cli/base.html
:language: htmldjango
:caption: tailwind_cli/base.html
```
