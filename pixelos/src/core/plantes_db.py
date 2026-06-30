# Pixel OS — Copyright 2026
# Free License — Verifiable and Reliable for Internet Users
# Pixel Software Design — Copyright 2026
"""Interface avec la base de donnees agronomique MySQL."""

import pymysql
import structlog

log = structlog.get_logger()

MYSQL_CFG = {
    "host": "localhost",
    "user": "agricol",
    "password": "agricol_secret",
    "database": "agricol",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}


class PlantesDB:
    """Requetes sur la base de donnees plantes."""
    def __init__(self):
        self.conn = None

    def _get_conn(self):
        if self.conn is None or not self.conn.open:
            self.conn = pymysql.connect(**MYSQL_CFG)
        return self.conn

    def _query(self, sql, params=None):
        c = self._get_conn().cursor()
        c.execute(sql, params or ())
        return c.fetchall()

    def _get(self, sql, params=None):
        rows = self._query(sql, params)
        return rows[0] if rows else None

    def list_plantes(self, categorie=None, cycle=None):
        sql = """SELECT p.id, p.nom_commun, p.nom_scientifique, p.cycle_vie,
                        c.nom as categorie
                 FROM plantes p
                 JOIN categories c ON p.id_categorie = c.id"""
        params = []
        conds = []
        if categorie:
            conds.append("c.nom = %s")
            params.append(categorie)
        if cycle:
            conds.append("p.cycle_vie = %s")
            params.append(cycle)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY p.nom_commun"
        return self._query(sql, params)

    def search(self, query):
        sql = """SELECT p.id, p.nom_commun, p.nom_scientifique, p.cycle_vie,
                        c.nom as categorie, f.nom as famille
                 FROM plantes p
                 JOIN categories c ON p.id_categorie = c.id
                 LEFT JOIN familles_botaniques f ON p.id_famille = f.id
                 WHERE p.nom_commun LIKE %s OR p.nom_scientifique LIKE %s
                 ORDER BY p.nom_commun LIMIT 30"""
        like = f"%{query}%"
        return self._query(sql, (like, like))

    def get_plante(self, ident):
        if ident and ident.isdigit():
            sql_id = "p.id = %s"
            param = int(ident)
        else:
            sql_id = "p.nom_commun = %s"
            param = ident

        row = self._get(f"""SELECT p.*, c.nom as categorie, f.nom as famille
                           FROM plantes p
                           JOIN categories c ON p.id_categorie = c.id
                           LEFT JOIN familles_botaniques f ON p.id_famille = f.id
                           WHERE {sql_id}""", (param,))
        if not row:
            return None

        # Get varieties
        row["varietes"] = self._query(
            "SELECT * FROM varietes WHERE id_plante = %s", (row["id"],))

        # Get calendars via varieties
        row["calendriers"] = self._query(
            """SELECT cc.* FROM calendrier_culture cc
               JOIN varietes v ON cc.id_variete = v.id
               WHERE v.id_plante = %s""", (row["id"],))

        # Get diseases
        row["maladies"] = self._query(
            """SELECT m.*, pm.sensibilite FROM maladies m
               JOIN plantes_maladies pm ON m.id = pm.id_maladie
               WHERE pm.id_plante = %s""", (row["id"],))

        # Get irrigation
        row["irrigations"] = self._query(
            """SELECT i.* FROM irrigation i
               JOIN varietes v ON i.id_variete = v.id
               WHERE v.id_plante = %s""", (row["id"],))

        return row

    def list_categories(self):
        return self._query(
            """SELECT c.*, COUNT(p.id) as nb_plantes
               FROM categories c
               LEFT JOIN plantes p ON p.id_categorie = c.id
               GROUP BY c.id ORDER BY c.nom""")

    def list_maladies(self, plante_query=None):
        if plante_query:
            like = f"%{plante_query}%"
            return self._query(
                """SELECT DISTINCT m.* FROM maladies m
                   JOIN plantes_maladies pm ON m.id = pm.id_maladie
                   JOIN plantes p ON p.id = pm.id_plante
                   WHERE p.nom_commun LIKE %s OR p.nom_scientifique LIKE %s
                   ORDER BY m.nom""", (like, like))
        return self._query("SELECT * FROM maladies ORDER BY nom")

    def get_calendrier(self, variete_query=None, filtres=None):
        sql = """SELECT v.nom as variete, cc.* FROM calendrier_culture cc
                 JOIN varietes v ON cc.id_variete = v.id
                 JOIN plantes p ON p.id = v.id_plante"""
        params = []
        conds = []
        if variete_query:
            conds.append("(v.nom LIKE %s OR p.nom_commun LIKE %s)")
            like = f"%{variete_query}%"
            params.extend([like, like])
        if filtres:
            if filtres.get("categorie"):
                conds.append("p.id_categorie = (SELECT id FROM categories WHERE nom = %s)")
                params.append(filtres["categorie"])
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY p.nom_commun, v.nom"
        return self._query(sql, params)

    def get_irrigation(self, variete_query=None, categorie=None):
        sql = """SELECT v.nom as variete, i.* FROM irrigation i
                 JOIN varietes v ON i.id_variete = v.id
                 JOIN plantes p ON p.id = v.id_plante"""
        params = []
        conds = []
        if variete_query:
            conds.append("(v.nom LIKE %s OR p.nom_commun LIKE %s)")
            like = f"%{variete_query}%"
            params.extend([like, like])
        if categorie:
            conds.append("p.id_categorie = (SELECT id FROM categories WHERE nom = %s)")
            params.append(categorie)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY p.nom_commun, v.nom"
        return self._query(sql, params)

    def close(self):
        if self.conn and self.conn.open:
            self.conn.close()
