from datetime import date

import pandas as pd


class Mandatos:
    """
    Responsável pelos mandatos presidenciais e pelos eventos de contexto.

    As datas são as de posse e de saída efetiva do cargo. Nos dois casos de
    afastamento por processo de impeachment, o vice passa a governar na data do
    afastamento (e não na data do julgamento final), porque é a partir daí que
    ele efetivamente exerce a Presidência.
    """

    MANDATOS = [
        {
            "id": "sarney",
            "presidente": "José Sarney",
            "rotulo": "Sarney",
            "inicio": date(1985, 3, 15),
            "fim": date(1990, 3, 14),
            "nota": "Assumiu como vice de Tancredo Neves, que morreu antes da posse.",
        },
        {
            "id": "collor",
            "presidente": "Fernando Collor",
            "rotulo": "Collor",
            "inicio": date(1990, 3, 15),
            "fim": date(1992, 10, 1),
            "nota": "Afastado em 02/10/1992 pela abertura do impeachment; renunciou em 29/12/1992.",
        },
        {
            "id": "itamar",
            "presidente": "Itamar Franco",
            "rotulo": "Itamar",
            "inicio": date(1992, 10, 2),
            "fim": date(1994, 12, 31),
            "nota": "Interino de 02/10/1992 a 29/12/1992, efetivado após a renúncia de Collor.",
        },
        {
            "id": "fhc1",
            "presidente": "Fernando Henrique Cardoso",
            "rotulo": "FHC 1",
            "inicio": date(1995, 1, 1),
            "fim": date(1998, 12, 31),
            "nota": "",
        },
        {
            "id": "fhc2",
            "presidente": "Fernando Henrique Cardoso",
            "rotulo": "FHC 2",
            "inicio": date(1999, 1, 1),
            "fim": date(2002, 12, 31),
            "nota": "",
        },
        {
            "id": "lula1",
            "presidente": "Luiz Inácio Lula da Silva",
            "rotulo": "Lula 1",
            "inicio": date(2003, 1, 1),
            "fim": date(2006, 12, 31),
            "nota": "",
        },
        {
            "id": "lula2",
            "presidente": "Luiz Inácio Lula da Silva",
            "rotulo": "Lula 2",
            "inicio": date(2007, 1, 1),
            "fim": date(2010, 12, 31),
            "nota": "",
        },
        {
            "id": "dilma1",
            "presidente": "Dilma Rousseff",
            "rotulo": "Dilma 1",
            "inicio": date(2011, 1, 1),
            "fim": date(2014, 12, 31),
            "nota": "",
        },
        {
            "id": "dilma2",
            "presidente": "Dilma Rousseff",
            "rotulo": "Dilma 2",
            "inicio": date(2015, 1, 1),
            "fim": date(2016, 5, 11),
            "nota": "Afastada em 12/05/2016 pela abertura do impeachment; cassada em 31/08/2016.",
        },
        {
            "id": "temer",
            "presidente": "Michel Temer",
            "rotulo": "Temer",
            "inicio": date(2016, 5, 12),
            "fim": date(2018, 12, 31),
            "nota": "Interino de 12/05/2016 a 31/08/2016, efetivado após o impeachment.",
        },
        {
            "id": "bolsonaro",
            "presidente": "Jair Bolsonaro",
            "rotulo": "Bolsonaro",
            "inicio": date(2019, 1, 1),
            "fim": date(2022, 12, 31),
            "nota": "",
        },
        {
            "id": "lula3",
            "presidente": "Luiz Inácio Lula da Silva",
            "rotulo": "Lula 3",
            "inicio": date(2023, 1, 1),
            "fim": date(2027, 1, 4),
            "nota": (
                "Mandato em curso: os resultados são parciais. Pela EC 111/2021, o próximo "
                "mandato começa em 05/01/2027."
            ),
        },
    ]

    # Fatos que ajudam a separar o que foi decisão de governo do que foi choque
    # externo ou herança. Não são juízo de valor sobre nenhum governo.
    EVENTOS = [
        (date(1986, 2, 28), "Plano Cruzado"),
        (date(1990, 3, 16), "Plano Collor (bloqueio da poupança)"),
        (date(1994, 7, 1), "Plano Real"),
        (date(1997, 7, 2), "Crise asiática"),
        (date(1998, 8, 17), "Crise russa"),
        (date(1999, 1, 15), "Câmbio flutuante"),
        (date(1999, 6, 21), "Início do regime de metas de inflação"),
        (date(2001, 6, 1), "Racionamento de energia"),
        (date(2002, 6, 1), "Crise de confiança pré-eleitoral"),
        (date(2008, 9, 15), "Crise financeira global"),
        (date(2014, 4, 1), "Início da recessão de 2014-16"),
        (date(2016, 12, 15), "Teto de gastos (EC 95)"),
        (date(2018, 5, 21), "Greve dos caminhoneiros"),
        (date(2020, 3, 11), "Pandemia de Covid-19"),
        (date(2021, 2, 24), "Autonomia do Banco Central"),
        (date(2022, 2, 24), "Guerra na Ucrânia"),
        (date(2023, 8, 30), "Novo arcabouço fiscal"),
    ]

    @classmethod
    def tabela(cls) -> pd.DataFrame:
        """Os mandatos em um DataFrame, com as datas como Timestamp e a ordem cronológica."""
        df = pd.DataFrame(cls.MANDATOS)
        df["inicio"] = pd.to_datetime(df["inicio"])
        df["fim"] = pd.to_datetime(df["fim"])
        df["ordem"] = range(len(df))
        return df

    @classmethod
    def ids(cls) -> list[str]:
        return [m["id"] for m in cls.MANDATOS]

    @classmethod
    def rotulo(cls, mandato_id: str) -> str:
        return next(m["rotulo"] for m in cls.MANDATOS if m["id"] == mandato_id)
