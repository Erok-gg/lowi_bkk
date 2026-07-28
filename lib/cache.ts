/**
 * cache.ts — Mémoïsation à durée de vie, pour les lectures de base.
 *
 * POURQUOI PAS `unstable_cache`. C'est l'outil naturel, mais il écrit dans le
 * Data Cache, plafonné à 2 Mo par entrée sur Vercel. Nos lectures pèsent
 * plusieurs mégaoctets : l'entrée serait silencieusement rejetée et rien ne
 * serait mis en cache — un cache qui ne cache pas est pire que pas de cache,
 * parce qu'on croit le problème réglé.
 *
 * On mémoïse donc en mémoire de processus. Portée : une instance serverless
 * chaude. Ce n'est pas un cache partagé, et c'est très bien ainsi : le but est
 * d'éviter qu'une même instance rejoue la même requête de 16 000 lignes vers
 * ap-southeast-1 à chaque navigation.
 *
 * CONTEXTE. Les pages sont en `force-dynamic` — obligatoire, l'accès dépend d'un
 * cookie — et refaisaient donc l'intégralité des requêtes à chaque chargement,
 * alors que les données ne bougent qu'au rythme des scraps, tous les 4 jours.
 *
 * La promesse est mémoïsée, pas son résultat : deux requêtes simultanées après
 * expiration partagent le même aller-retour au lieu d'en lancer deux. En cas
 * d'échec, l'entrée est purgée pour que l'erreur ne soit pas servie en boucle.
 */

/** Durée de vie par défaut. Les scraps tournent tous les 4 jours : une heure de
 *  retard est invisible à l'usage, et divise les requêtes par le nombre de pages
 *  consultées dans l'heure. */
export const DEFAULT_TTL_MS = 60 * 60 * 1000;

interface Entry<T> {
  expires: number;
  value: Promise<T>;
}

const store = new Map<string, Entry<unknown>>();

/**
 * Enveloppe une fonction asynchrone sans argument dans un cache à expiration.
 * `key` doit être stable et unique.
 */
export function memoTTL<T>(
  key: string,
  fn: () => Promise<T>,
  ttlMs: number = DEFAULT_TTL_MS
): () => Promise<T> {
  return () => {
    const now = Date.now();
    const hit = store.get(key) as Entry<T> | undefined;
    if (hit && hit.expires > now) return hit.value;

    const value = fn().catch((e) => {
      // Une erreur ne doit pas rester en cache jusqu'à expiration.
      store.delete(key);
      throw e;
    });
    store.set(key, { expires: now + ttlMs, value });
    return value;
  };
}

/** Vide le cache (tests, ou après un scrape déclenché à la main). */
export function clearCache(): void {
  store.clear();
}
