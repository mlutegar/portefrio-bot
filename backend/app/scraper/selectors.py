# Seletores CSS e XPath para automação com o Playwright no Portal Multiplike.
# Modifique os valores aqui caso a estrutura do portal seja alterada.

SELECTORS = {
    "login": {
        "email": [
            "[data-testid=login-form-email-input]",
            "#username",
            "input[type=email]",
            "input[name=username]",
            "input[name*=email i]",
            "input[name*=user i]",
            "input[name*=login i]",
        ],
        "senha": [
            "[data-testid=login-form-password-input]",
            "#password",
            "input[type=password]",
            "input[name=password]",
        ],
        "submit": [
            "[data-testid=login-form-submit-button]",
            "#kc-login",
            "button[type=submit]",
            "input[type=submit]",
            "button:has-text('Entrar')",
            "button:has-text('Login')",
            "button:has-text('Acessar')",
        ],
        "confirmar_2fa": [
            "button[type=submit]",
            "button:has-text('Confirmar')",
            "button:has-text('Validar')",
            "button:has-text('Entrar')",
        ]
    },
    "busca_cnpj": {
        "input_cnpj": [
            "input[name*=cnpj i]",
            "input[id*=cnpj i]",
            "input[placeholder*=cnpj i]",
            "input[type=search]",
            "input[type=text]",
        ],
        "input_cnpj_fallback": [
            "input[type=text]",
            "input[type=search]"
        ],
        "submit": [
            "button:has-text('Buscar')",
            "button:has-text('Pesquisar')",
            "button:has-text('Consultar')",
            "button[type=submit]",
        ]
    },
    "score_navigation": {
        "ir_para_cedente": [
            "text='Ir para portal do cedente'",
            "button:has-text('Ir para portal do cedente')",
            "a:has-text('Ir para portal do cedente')",
            "[data-testid*=cedente i]",
            "text='Cedente'",
        ],
        "card_containers": [
            ".card",
            ".panel",
            "div",
            "section",
        ],
        "clique_aqui_fallback": [
            "text='Clique aqui'",
            "a:has-text('Clique aqui')",
            "button:has-text('Clique aqui')",
            "a:has-text('Score')",
        ]
    }
}
