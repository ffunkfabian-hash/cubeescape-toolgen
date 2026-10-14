using System.Collections;
using UnityEngine;
using UnityEngine.Events;

/// <summary>Explicit one-shot playback for the exported transform animation.
/// Attach beside a Legacy Animation component on the imported asset root.
/// Call ApplyGrab from an interaction event; no input or physics is inferred.
/// </summary>
[DisallowMultipleComponent]
[RequireComponent(typeof(Animation))]
public sealed class MagnetGripperActionPlayer : MonoBehaviour
{
    private const string ClipName = "MG_Apply";
    [SerializeField] private AnimationClip applyClip;
    [SerializeField] private UnityEvent onGripClosed = new UnityEvent();
    [SerializeField] private UnityEvent onApplicationFinished = new UnityEvent();

    private Animation playback;
    private AnimationClip runtimeClip;
    private Coroutine running;

    private void Awake()
    {
        playback = GetComponent<Animation>();
        playback.playAutomatically = false;
        playback.Stop();
        if (applyClip == null) return;
        // Work on an instance: never mutate the shared imported asset.
        runtimeClip = Instantiate(applyClip);
        runtimeClip.legacy = true;
        runtimeClip.wrapMode = WrapMode.Once;
        playback.AddClip(runtimeClip, ClipName);
        SetIdlePose();
    }

    public void ApplyGrab() => TryApplyGrab();

    public bool TryApplyGrab()
    {
        if (!isActiveAndEnabled || runtimeClip == null || running != null) return false;
        AnimationState state = playback[ClipName];
        state.time = 0f;
        state.speed = 1f;
        state.wrapMode = WrapMode.Once;
        playback.Play(ClipName, PlayMode.StopSameLayer);
        running = StartCoroutine(WaitForApplication());
        return true;
    }

    private IEnumerator WaitForApplication()
    {
        bool notified = false;
        while (playback.IsPlaying(ClipName))
        {
            if (!notified && playback[ClipName].time >= 0.5f)
            {
                notified = true;
                onGripClosed.Invoke();
            }
            yield return null;
        }
        running = null;
        SetIdlePose();
        onApplicationFinished.Invoke();
    }

    public void CancelAction()
    {
        if (running != null) StopCoroutine(running);
        running = null;
        SetIdlePose();
    }

    private void SetIdlePose()
    {
        if (playback == null || runtimeClip == null) return;
        playback.Stop(ClipName);
        AnimationState state = playback[ClipName];
        state.time = 0f;
        state.weight = 1f;
        state.enabled = true;
        playback.Sample();
        state.enabled = false;
    }

    private void OnDisable() => CancelAction();

    private void OnDestroy()
    {
        if (runtimeClip != null) Destroy(runtimeClip);
    }
}
