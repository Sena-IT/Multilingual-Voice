# # consumers/clear_on_barge_in.py
# import asyncio
# from pipecat.consumer import Consumer
# from pipecat.frames import CancelFrame

# BARGE_IN_FRAMES = {
#     "StartInterruptionFrame",   # Pipecat ≤ v0.28
#     "InterruptStartFrame",      # Pipecat >= v0.29
#     "BargeInFrame",            # fallback, some forks
# }

# class ClearAudioOnBargeIn(Consumer):
#     async def consume(self, frame, task):
#         # Pass the frame downstream unchanged
#         yield frame

#         # If this is Pipecat’s “user started talking” marker → flush
#         if frame.__class__.__name__ in BARGE_IN_FRAMES:
#             await task.queue_frames([CancelFrame()])
