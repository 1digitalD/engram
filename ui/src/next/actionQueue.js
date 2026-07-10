/** Serialize async affordance saves so overlapping refetches cannot clobber each other. */
export function createActionQueue() {
  let tail = Promise.resolve();
  return function enqueue(task) {
    const run = tail.then(() => task(), () => task());
    tail = run.catch(() => {});
    return run;
  };
}
