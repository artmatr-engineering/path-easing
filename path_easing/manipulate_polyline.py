import numpy as np
np.set_printoptions(suppress=True)

def extend_or_sample_polyline(points, dist_start, dist_end):
    """Extends or samples a polyline based on distances from the start and end points."""
    seg_lengths = np.sqrt(np.sum(np.diff(points, axis=0)**2, axis=1))
    cum_dist = np.insert(np.cumsum(seg_lengths), 0, 0)

    if dist_start < 0 and dist_end < 0 and abs(dist_start + dist_end) > cum_dist[-1]:
        segment_idx = np.searchsorted(cum_dist, abs(dist_start) / (abs(dist_start) + abs(dist_end)) * cum_dist[-1], side='right') - 1
        alpha = (abs(dist_start) / (abs(dist_start) + abs(dist_end)) * cum_dist[-1] - cum_dist[segment_idx]) / seg_lengths[segment_idx]
        new_point = (1 - alpha) * points[segment_idx] + alpha * points[segment_idx + 1]
        return np.array([new_point])

    direction_start = (points[1] - points[0]) / np.linalg.norm(points[1] - points[0])
    direction_end = (points[-1] - points[-2]) / np.linalg.norm(points[-1] - points[-2])

    if dist_start < 0:
        segment_idx = np.searchsorted(cum_dist, -dist_start, side='right') - 1
        alpha = (-dist_start - cum_dist[segment_idx]) / seg_lengths[segment_idx]
        new_start = (1 - alpha) * points[segment_idx] + alpha * points[segment_idx + 1]
        points = np.vstack((new_start, points[segment_idx + 1:]))

        # Update segment lengths and cumulative distance after modifying the start
        seg_lengths = np.sqrt(np.sum(np.diff(points, axis=0)**2, axis=1))
        cum_dist = np.insert(np.cumsum(seg_lengths), 0, 0)

    else:
        new_start = points[0] - dist_start * direction_start
        points = np.vstack((new_start, points))

    direction_end = (points[-1] - points[-2]) / np.linalg.norm(points[-1] - points[-2])

    if dist_end < 0:
        segment_idx = np.searchsorted(cum_dist, cum_dist[-1] + dist_end, side='right') - 1
        alpha = (cum_dist[-1] + dist_end - cum_dist[segment_idx]) / seg_lengths[segment_idx]
        new_end = (1 - alpha) * points[segment_idx] + alpha * points[segment_idx + 1]
        points = np.vstack((points[:segment_idx + 1], new_end))
    else:
        new_end = points[-1] + dist_end * direction_end
        points = np.vstack((points, new_end))

    return points


def cull_duplicates(polyline):
    """Ensures that a polyine has no duplicate consecutive vertices."""
    # Find the indices of unique rows
    _, idx = np.unique(polyline, axis=0, return_index=True)

    # Sort the indices and use them to take the corresponding rows of polyline
    polyline_unique = polyline[np.sort(idx)]

    return polyline_unique


def stack_polylines(polylines):
    """Ensures that a polyine has no consecutive vertices with duplicate xy coordinates.
    Vertices closer to the start will have priority over vertices closer to the end. """
    # Vertically stack all polylines
    stacked_polyline = np.vstack(polylines)
    
    # Find indices of consecutive duplicate points
    dup_indices = np.where(np.all(stacked_polyline[1:] == stacked_polyline[:-1], axis=1))
    
    # Delete the duplicate points
    return np.delete(stacked_polyline, dup_indices, axis=0)


def split_polyline(points, dist_start, dist_end):
    """Splits a polyline into three segments based on distances from the start and end points."""
    # Calculate cumulative distance along the polyline
    seg_lengths = np.sqrt(np.sum(np.diff(points, axis=0)**2, axis=1))
    cum_dist = np.insert(np.cumsum(seg_lengths), 0, 0)

    # Check if distances are valid
    if dist_start < 0 or dist_end < 0:
        raise ValueError("Invalid distances. Only positive distances are allowed.")
    
    # Check for special case where sum of distances exceeds polyline length
    if dist_start + dist_end > cum_dist[-1]:
        # Calculate the normalized split point
        split_ratio = dist_start / (dist_start + dist_end)
        split_segment_idx = np.searchsorted(cum_dist, split_ratio * cum_dist[-1], side='right') - 1

        alpha_split = (split_ratio * cum_dist[-1] - cum_dist[split_segment_idx]) / seg_lengths[split_segment_idx]
        point_split = (1 - alpha_split) * points[split_segment_idx] + alpha_split * points[split_segment_idx + 1]

        # Split the polyline into three segments
        polyline_1 = np.vstack((points[:split_segment_idx + 1], point_split))
        polyline_2 = None
        polyline_3 = np.vstack((point_split, points[split_segment_idx + 1:]))
    else:
        # Normal case: find the segments that contain the start and end points
        start_segment_idx = np.searchsorted(cum_dist, dist_start, side='right') - 1
        end_segment_idx = np.searchsorted(cum_dist, cum_dist[-1] - dist_end, side='right') - 1

        # Linearly interpolate the start and end points
        alpha_start = (dist_start - cum_dist[start_segment_idx]) / seg_lengths[start_segment_idx]
        alpha_end = (cum_dist[-1] - dist_end - cum_dist[end_segment_idx]) / seg_lengths[end_segment_idx]

        point_start = (1 - alpha_start) * points[start_segment_idx] + alpha_start * points[start_segment_idx + 1]
        point_end = (1 - alpha_end) * points[end_segment_idx] + alpha_end * points[end_segment_idx + 1]

        # Split the polyline into three segments
        polyline_1 = cull_duplicates(np.vstack((points[:start_segment_idx + 1], point_start)))
        polyline_2 = cull_duplicates(np.vstack((point_start, points[start_segment_idx + 1:end_segment_idx + 1], point_end)))
        polyline_3 = cull_duplicates(np.vstack((point_end, points[end_segment_idx + 1:])))
    
    return polyline_1, polyline_2, polyline_3


def apply_height_differential(points, start_height_offset, end_height_offset):
    """Moves the ends of a polyline vertically by given amounts and interpolates the z values of the points in between"""
    # Calculate the total distance of the polyline
    seg_lengths = np.sqrt(np.sum(np.diff(points, axis=0)**2, axis=1))
    total_dist = np.sum(seg_lengths)

    # Calculate the relative distance along the polyline for each point
    rel_dist = np.insert(np.cumsum(seg_lengths), 0, 0) / total_dist

    # Interpolate the z values along the line
    new_z_values = np.interp(rel_dist, [0, 1], [start_height_offset, end_height_offset])
    
    # Create a new array for the updated points
    new_points = points.copy()
    
    # Assign the new z values
    new_points[:, 2] = new_z_values
    
    return new_points


def manipulate_polyline(poly, params):
    """Main function for manipulating a polyline for use with brushes on a 3-axis machine"""
    # Convert the 2D polyline to 3D
    poly3d = np.insert(poly, 2, values=0, axis=1)

    # Remove any duplicate vertices
    poly3d = cull_duplicates(poly3d)

    # Apply the shifts to the polyline
    poly3d_w_shift = extend_or_sample_polyline(poly3d, params['start_shift'], params['end_shift'])

    # Apply the extensions to the polyline
    poly3d_ext = extend_or_sample_polyline(poly3d, params['start_extend'], params['end_extend'])

    # Apply the height offsets to the extended polyline
    poly3d_ext[0, 2] += params['start_extend_height']
    poly3d_ext[-1, 2] += params['end_extend_height']

    if len(poly3d_w_shift) == 1:
        # The shifts converged to a point; skip the pushthrough application
        print('Warning: polyline shifts converged to a point and z pushthrough application was skipped')
        final_polyline = stack_polylines((poly3d_ext[0], poly3d_w_shift, poly3d_ext[-1]))
    else:
        # Apply the pushthrough insets
        start_push, mid_push, end_push = split_polyline(poly3d_w_shift, params['start_pushthrough_inset'], params['end_pushthrough_inset'])

        # Apply the Z pushthroughs
        start_push = apply_height_differential(start_push, 0, params['start_pushthrough_z'])
        end_push = apply_height_differential(end_push, params['end_pushthrough_z'], 0)
        if mid_push is not None:
            mid_push = apply_height_differential(mid_push, params['start_pushthrough_z'], params['end_pushthrough_z'])
            final_polyline = stack_polylines((poly3d_ext[0], start_push, mid_push, end_push, poly3d_ext[-1]))
        else:
            final_polyline = stack_polylines((poly3d_ext[0], start_push, end_push, poly3d_ext[-1]))
    
    return final_polyline

if __name__ == '__main__':

    # Parameters for polyline manipulation
    params = {
        'start_shift': 1,
        'end_shift': 0,
        'start_extend': 5,
        'end_extend': 5,
        'start_extend_height': 5,
        'end_extend_height': 5,
        'start_pushthrough_inset': 2,
        'end_pushthrough_inset': 7,
        'start_pushthrough_z': -3,
        'end_pushthrough_z': -2
    }

    # Polyline definition
    poly = np.array([[158.24548867, 209.37744251],
                    [157.76852081, 208.77645448],
                    [157.2688602,  208.26624988],
                    [156.74786094, 207.84000205],
                    [156.20687713, 207.49088435],
                    [155.64726286, 207.21207014],
                    [155.07037224, 206.99673276],
                    [154.47755936, 206.83804558],
                    [153.87017832, 206.72918195],
                    [153.24958322, 206.66331523],
                    [152.61712815, 206.63361876],
                    [151.97416722, 206.6332659 ],
                    [151.32205452, 206.65543001],
                    [150.66214415, 206.69328444],
                    [149.99579021, 206.74000254],
                    [149.32434679, 206.78875768],
                    [148.649168,   206.83272319],
                    [147.97160793, 206.86507245],
                    [147.29302068, 206.8789788 ],
                    [146.61476034, 206.8676156 ],
                    [145.93818102, 206.8241562 ],
                    [145.26463682, 206.74177396],
                    [144.59548182, 206.61364222],
                    [143.93207014, 206.43293436],
                    [143.27575586, 206.19282371],
                    [142.62789309, 205.88648364]])
    
    m_poly = manipulate_polyline(poly, params)
    print(m_poly)