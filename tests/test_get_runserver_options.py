from django_tailwind_cli.management.commands.tailwind import get_runserver_options


def test_get_runserver_options_defaults():
    options = get_runserver_options()
    assert options == []


def test_get_runserver_options_with_addrport():
    options = get_runserver_options(addrport="127.0.0.1:8000")
    assert options == ["127.0.0.1:8000"]


def test_get_runserver_options_with_ipv6():
    options = get_runserver_options(use_ipv6=True)
    assert options == ["--ipv6"]


def test_get_runserver_options_with_no_threading():
    options = get_runserver_options(no_threading=True)
    assert options == ["--nothreading"]


def test_get_runserver_options_with_no_static():
    options = get_runserver_options(no_static=True)
    assert options == ["--nostatic"]


def test_get_runserver_options_with_no_reloader():
    options = get_runserver_options(no_reloader=True)
    assert options == ["--noreload"]


def test_get_runserver_options_with_skip_checks():
    options = get_runserver_options(skip_checks=True)
    assert options == ["--skip-checks"]


def test_get_runserver_options_with_pdb():
    options = get_runserver_options(pdb=True)
    assert options == ["--pdb"]


def test_get_runserver_options_with_ipdb():
    options = get_runserver_options(ipdb=True)
    assert options == ["--ipdb"]


def test_get_runserver_options_with_pm():
    options = get_runserver_options(pm=True)
    assert options == ["--pm"]


def test_get_runserver_options_with_print_sql():
    options = get_runserver_options(print_sql=True)
    assert options == ["--print-sql"]


def test_get_runserver_options_with_print_sql_location():
    options = get_runserver_options(print_sql_location=True)
    assert options == ["--print-sql-location"]


def test_get_runserver_options_with_cert_file():
    options = get_runserver_options(cert_file="/path/to/cert.crt")
    assert options == ["--cert-file=/path/to/cert.crt"]


def test_get_runserver_options_with_key_file():
    options = get_runserver_options(key_file="/path/to/key.key")
    assert options == ["--key-file=/path/to/key.key"]


def test_get_runserver_options_with_all_options():
    options = get_runserver_options(
        addrport="127.0.0.1:8000",
        use_ipv6=True,
        no_threading=True,
        no_static=True,
        no_reloader=True,
        skip_checks=True,
        pdb=True,
        ipdb=True,
        pm=True,
        print_sql=True,
        print_sql_location=True,
        cert_file="/path/to/cert.crt",
        key_file="/path/to/key.key",
    )
    assert options == [
        "--ipv6",
        "--nothreading",
        "--nostatic",
        "--noreload",
        "--skip-checks",
        "--pdb",
        "--ipdb",
        "--pm",
        "--print-sql",
        "--print-sql-location",
        "--cert-file=/path/to/cert.crt",
        "--key-file=/path/to/key.key",
        "127.0.0.1:8000",
    ]
