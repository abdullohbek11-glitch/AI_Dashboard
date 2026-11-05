/** @odoo-module **/
// Collects requests made within a short window into one call (widgets that become visible together share one RPC).

/**
 * `flush(keys)` receives the distinct keys and returns a Promise of `{key: result}`.
 * `request(key)` resolves with that key's result.
 */
export function createBatcher(flush, delayMs = 25) {
    let pending = new Map();
    let timer = null;

    async function run() {
        const batch = pending;
        pending = new Map();
        timer = null;
        try {
            const results = await flush([...batch.keys()]);
            for (const [key, waiters] of batch) {
                waiters.forEach((w) => w.resolve(results[key]));
            }
        } catch (error) {
            for (const waiters of batch.values()) {
                waiters.forEach((w) => w.reject(error));
            }
        }
    }

    return {
        request(key) {
            return new Promise((resolve, reject) => {
                if (!pending.has(key)) {
                    pending.set(key, []);
                }
                pending.get(key).push({ resolve, reject });
                if (timer === null) {
                    timer = setTimeout(run, delayMs);
                }
            });
        },
    };
}
